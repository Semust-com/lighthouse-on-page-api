// Run Lighthouse on a page with the Semust Lighthouse & On-Page API (Go 1.21+, standard library only).
//
//	export SEMUST_API_USER=... SEMUST_API_PASSWORD=...
//	go run . https://www.wikipedia.org/ desktop
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"time"
)

const (
	api  = "https://data.semust.com"
	wait = 60 // seconds the API holds the request open before answering 202
)

type lighthouse struct {
	Data struct {
		FinalURL          string `json:"final_url"`
		LighthouseVersion string `json:"lighthouse_version"`
		Scores            struct {
			Performance   *int `json:"performance"`
			Accessibility *int `json:"accessibility"`
			BestPractices *int `json:"best_practices"`
			SEO           *int `json:"seo"`
		} `json:"scores"`
		Metrics *struct {
			LCP *int     `json:"largest_contentful_paint_ms"`
			CLS *float64 `json:"cumulative_layout_shift"`
			TBT *int     `json:"total_blocking_time_ms"`
		} `json:"metrics"`
		FailedAudits []struct {
			Category     string  `json:"category"`
			Title        string  `json:"title"`
			DisplayValue *string `json:"display_value"`
		} `json:"failed_audits"`
	} `json:"data"`
	Cost float64 `json:"cost"`
}

var client = &http.Client{Timeout: (wait + 30) * time.Second}

func send(method, url string, body []byte) (*http.Response, []byte, error) {
	req, err := http.NewRequest(method, url, bytes.NewReader(body))
	if err != nil {
		return nil, nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("SEMUST-API-USER", os.Getenv("SEMUST_API_USER"))
	req.Header.Set("SEMUST-API-PASSWORD", os.Getenv("SEMUST_API_PASSWORD"))
	resp, err := client.Do(req)
	if err != nil {
		return nil, nil, err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(resp.Body)
	return resp, data, err
}

// call POSTs a request and returns the final response, polling if the API answers 202.
func call(path string, payload any) (int, []byte, error) {
	body, _ := json.Marshal(payload)
	resp, data, err := send(http.MethodPost, fmt.Sprintf("%s%s?wait=%d", api, path, wait), body)
	for err == nil && resp.StatusCode == http.StatusAccepted {
		var task struct {
			PollURL string `json:"poll_url"`
		}
		if err = json.Unmarshal(data, &task); err != nil {
			break
		}
		retry, convErr := strconv.Atoi(resp.Header.Get("Retry-After"))
		if convErr != nil {
			retry = 5
		}
		time.Sleep(time.Duration(retry) * time.Second)
		resp, data, err = send(http.MethodGet, task.PollURL, nil)
	}
	if err != nil {
		return 0, nil, err
	}
	return resp.StatusCode, data, nil
}

func show(p *int) string {
	if p == nil {
		return "-"
	}
	return strconv.Itoa(*p)
}

func main() {
	url, device := "https://www.wikipedia.org/", "desktop"
	if len(os.Args) > 1 {
		url = os.Args[1]
	}
	if len(os.Args) > 2 {
		device = os.Args[2]
	}
	status, data, err := call("/v1/on-page", map[string]any{
		"type":   "lighthouse", // or "audit" / "content"
		"url":    url,
		"device": device, // "mobile" (the API default) or "desktop"
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, "request failed:", err)
		os.Exit(1)
	}
	if status != http.StatusOK {
		fmt.Fprintf(os.Stderr, "Error %d: %s\n", status, data)
		os.Exit(1)
	}

	var r lighthouse
	if err := json.Unmarshal(data, &r); err != nil {
		fmt.Fprintln(os.Stderr, "decode:", err)
		os.Exit(1)
	}
	d := r.Data
	fmt.Printf("%s · %s · Lighthouse %s\n", d.FinalURL, device, d.LighthouseVersion)
	fmt.Printf("  performance %s · accessibility %s · best practices %s · SEO %s\n",
		show(d.Scores.Performance), show(d.Scores.Accessibility), show(d.Scores.BestPractices), show(d.Scores.SEO))
	if m := d.Metrics; m != nil && m.CLS != nil {
		fmt.Printf("  LCP %s ms · CLS %g · TBT %s ms\n", show(m.LCP), *m.CLS, show(m.TBT))
	}
	for _, a := range d.FailedAudits {
		extra := ""
		if a.DisplayValue != nil {
			extra = " (" + *a.DisplayValue + ")"
		}
		fmt.Printf("  [%s] %s%s\n", a.Category, a.Title, extra)
	}
	fmt.Printf("\nCost: $%g\n", r.Cost)
}
