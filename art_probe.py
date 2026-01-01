#!/usr/bin/env python3


import asyncio
import aiohttp
import argparse
import time
import sys
import statistics
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse

DEFAULT_MAX_REQUESTS = 100
START_BATCH_SIZE = 5
BATCH_INCREMENT = 5
LATENCY_THRESHOLD_MULTIPLIER = 3.0
TIMEOUT_SECONDS = 10

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

@dataclass
class RequestMetric:
    req_id: int
    status: int
    latency_ms: float
    size_bytes: int
    error: Optional[str] = None

class AdaptiveRateLimiter:
    def __init__(self, url: str, method: str, headers: Dict, max_requests: int):
        self.url = url
        self.method = method
        self.headers = headers
        self.max_requests = max_requests
        
        self.total_requests_sent = 0
        self.metrics: List[RequestMetric] = []
        
        self.baseline_latency = 0.0
        self.baseline_status = 200
        self.is_baseline_set = False
        
        self.stop_reason = None
        self.verdict = "INCONCLUSIVE"

    async def _send_single_request(self, session: aiohttp.ClientSession, req_id: int) -> RequestMetric:
        """Performs a single async HTTP request and measures metrics."""
        start_time = time.perf_counter()
        try:
            async with session.request(
                method=self.method, 
                url=self.url, 
                headers=self.headers, 
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
            ) as response:
                await response.read()
                end_time = time.perf_counter()
                
                return RequestMetric(
                    req_id=req_id,
                    status=response.status,
                    latency_ms=(end_time - start_time) * 1000,
                    size_bytes=response.content_length or 0
                )
        except Exception as e:
            end_time = time.perf_counter()
            return RequestMetric(
                req_id=req_id,
                status=0,
                latency_ms=(end_time - start_time) * 1000,
                size_bytes=0,
                error=str(e)
            )

    def _analyze_batch(self, batch_metrics: List[RequestMetric]) -> bool:
        """
        Analyzes the latest batch against the baseline.
        Returns True if testing should STOP.
        """
        valid_reqs = [m for m in batch_metrics if m.status != 0]
        
        if not valid_reqs:
            print(f"{Colors.WARNING}[!] Batch failed (connection errors). Stopping.{Colors.ENDC}")
            self.stop_reason = "Connection Instability"
            return True

        avg_latency = statistics.mean([m.latency_ms for m in valid_reqs])
        status_codes = {m.status for m in valid_reqs}
        
        if not self.is_baseline_set:
            self.baseline_latency = avg_latency
            self.baseline_status = statistics.mode([m.status for m in valid_reqs])
            self.is_baseline_set = True
            print(f"{Colors.OKBLUE}[i] Baseline Established:{Colors.ENDC} {self.baseline_latency:.2f}ms | Status: {self.baseline_status}")
            return False

        if 429 in status_codes:
            self.verdict = "HARD RATE LIMITING DETECTED"
            self.stop_reason = "HTTP 429 Response Observed"
            return True

        current_mode_status = statistics.mode([m.status for m in valid_reqs])
        if current_mode_status != self.baseline_status:
            self.verdict = "SOFT RATE LIMITING (BLOCKING) DETECTED"
            self.stop_reason = f"Status code shifted from {self.baseline_status} to {current_mode_status}"
            return True

        if avg_latency > (self.baseline_latency * LATENCY_THRESHOLD_MULTIPLIER):
            self.verdict = "SOFT RATE LIMITING (THROTTLING) DETECTED"
            self.stop_reason = f"Latency spiked to {avg_latency:.2f}ms (Baseline: {self.baseline_latency:.2f}ms)"
            return True

        return False

    async def run(self):
        print(f"{Colors.HEADER}[*] Starting Adaptive Rate Limit Test{Colors.ENDC}")
        print(f"[*] Target: {self.method} {self.url}")
        print(f"[*] Safety Cap: {self.max_requests} requests")
        print("-" * 60)

        async with aiohttp.ClientSession() as session:
            current_batch_size = START_BATCH_SIZE
            
            while self.total_requests_sent < self.max_requests:
                remaining = self.max_requests - self.total_requests_sent
                count = min(current_batch_size, remaining)
                
                if count <= 0:
                    break

                print(f"[*] Sending batch of {count} requests...", end='', flush=True)
                
                tasks = []
                for _ in range(count):
                    self.total_requests_sent += 1
                    tasks.append(self._send_single_request(session, self.total_requests_sent))
                
                batch_results = await asyncio.gather(*tasks)
                self.metrics.extend(batch_results)
                
                print(f" Done.")
                
                should_stop = self._analyze_batch(batch_results)
                
                if should_stop:
                    print(f"\n{Colors.FAIL}[!] STOPPING: {self.stop_reason}{Colors.ENDC}")
                    break
                
                current_batch_size += BATCH_INCREMENT
                await asyncio.sleep(0.5)

            if not self.stop_reason and self.total_requests_sent >= self.max_requests:
                self.verdict = "NO RATE LIMIT DETECTED"
                self.stop_reason = "Reached maximum request limit with stable behavior"

        self._print_report()

    def _print_report(self):
        print("\n" + "="*60)
        print(f"{Colors.BOLD}FINAL TEST REPORT{Colors.ENDC}")
        print("="*60)
        print(f"Total Requests Sent : {self.total_requests_sent}")
        print(f"Baseline Latency    : {self.baseline_latency:.2f}ms")
        
        if self.metrics:
            valid_metrics = [m.latency_ms for m in self.metrics if m.status != 0]
            if valid_metrics:
                final_avg = statistics.mean(valid_metrics)
                print(f"Average Latency     : {final_avg:.2f}ms")
        
        print("-" * 60)
        print(f"VERDICT: {Colors.BOLD}{self.verdict}{Colors.ENDC}")
        if self.stop_reason:
            print(f"Reason : {self.stop_reason}")
        print("="*60)
        
        print(f"\n{Colors.HEADER}LIMITATIONS OF FINDINGS:{Colors.ENDC}")
        print("1. Results apply only to the specific source IP used.")
        print(f"2. Testing stopped at {self.max_requests} requests; limits may exist at higher thresholds.")
        print("3. Time window was short; long-term sliding window limits may not be triggered.")
        print("4. Network jitter can occasionally mimic throttling.")

def parse_args():
    parser = argparse.ArgumentParser(
        description="ART Probe - Adaptive Rate Limit Testing Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://api.example.com/endpoint
  %(prog)s https://api.example.com/login -m POST
  %(prog)s https://api.example.com/endpoint -H "Authorization: Bearer token"
  %(prog)s https://api.example.com/endpoint --max 200

For more information, visit: https://github.com/aminebensalha/art-probe
        """
    )
    
    parser.add_argument("url", help="Target URL (e.g., https://api.example.com/login)")
    parser.add_argument("-m", "--method", default="GET", choices=["GET", "POST", "PUT", "DELETE"], 
                        help="HTTP Method (default: GET)")
    parser.add_argument("-H", "--header", action="append", 
                        help="Add header (format: 'Key: Value'). Can be used multiple times.")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_REQUESTS, 
                        help=f"Maximum total requests to send (safety cap, default: {DEFAULT_MAX_REQUESTS})")
    parser.add_argument("-v", "--version", action="version", version="ART Probe v1.0.0")
    
    return parser.parse_args()

def parse_headers_list(header_list: List[str]) -> Dict[str, str]:
    headers = {}
    if header_list:
        for h in header_list:
            if ":" in h:
                key, value = h.split(":", 1)
                headers[key.strip()] = value.strip()
            else:
                print(f"{Colors.WARNING}[!] Warning: Invalid header format '{h}'. Ignored.{Colors.ENDC}")
    
    if "User-Agent" not in headers:
        headers["User-Agent"] = "ART-Probe/1.0 (Security Research)"
        
    return headers

if __name__ == "__main__":
    args = parse_args()
    
    parsed_url = urlparse(args.url)
    if not parsed_url.scheme or not parsed_url.netloc:
        print(f"{Colors.FAIL}[!] Error: Invalid URL. Please include scheme (http/https).{Colors.ENDC}")
        sys.exit(1)

    headers = parse_headers_list(args.header)
    
    tester = AdaptiveRateLimiter(
        url=args.url, 
        method=args.method, 
        headers=headers, 
        max_requests=args.max
    )
    
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(tester.run())
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}[!] Test interrupted by user.{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.FAIL}[!] Unexpected error: {e}{Colors.ENDC}")
