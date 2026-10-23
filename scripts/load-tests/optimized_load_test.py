#!/usr/bin/env python3
"""
Optimized Load Testing for Desarrollo Créditos API
Realistic traffic simulation with gradual ramp-up, safe concurrency, and think time.
"""

import asyncio
import aiohttp
import json
import time
import random
import logging
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('optimized_load_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    total_requests: int
    successful: int
    failed: int
    duration: float
    rps: float
    avg_response_time_ms: float
    success_rate: float
    max_concurrency_reached: int

class OptimizedLoadTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.start_time = time.time()
        
        # Optimized testing parameters
        self.ramp_up_duration = 60  # seconds to reach max load
        self.max_concurrency = 50    # safe maximum concurrent users
        self.min_concurrency = 10    # start with 10 users
        self.think_time_min = 0.5    # 0.5s - 2.5s random delay between requests
        self.think_time_max = 2.5
        self.request_timeout = 10    # generous timeout
        
        # Test data
        self.test_payload = {
            "tipo_id": "1",
            "numero_id": f"{random.randint(1000000000, 9999999999)}",
            "primer_apellido": "Ficticio",
            "ocupacion": "Empleado",
            "tipo_contrato": "Indefinido",
            "fecha_nacimiento": "1990-05-15",
            "ingresos_mensuales": 5000000,
            "saldo_financiar": 10000000,
            "plazo": 36,
            "tasa": 2
        }

    def calculate_concurrency_at_time(self, current_time: float) -> int:
        """Calculate current concurrency based on ramp-up curve"""
        elapsed = current_time - self.start_time
        
        if elapsed <= 0:
            return self.min_concurrency
            
        progress = min(elapsed / self.ramp_up_duration, 1.0)
        
        # Smooth step function for realistic ramp-up
        if progress < 0.3:
            # Slow start: 10 → 20 users
            return int(self.min_concurrency + (progress * 10 / 0.3))
        elif progress < 0.7:
            # Medium ramp: 20 → 50 users
            return int(20 + ((progress - 0.3) * 30 / 0.4))
        else:
            # Max load: 50 users
            return self.max_concurrency

    async def make_request_with_think_time(self, request_id: int) -> Dict[str, Any]:
        """Make a single request with realistic think time before it"""
        # Random think time to simulate human behavior
        await asyncio.sleep(random.uniform(self.think_time_min, self.think_time_max))
        
        try:
            current_time = time.time()
            current_concurrency = self.calculate_concurrency_at_time(current_time)
            
            async with self.session.post(
                f"{self.base_url}/api/motor/evaluar",
                json=self.test_payload,
                timeout=aiohttp.ClientTimeout(total=self.request_timeout)
            ) as response:
                response_data = await response.json()
                
                return {
                    "request_id": request_id,
                    "status_code": response.status,
                    "response": response_data,
                    "success": response.status == 200,
                    "timestamp": datetime.fromtimestamp(current_time).isoformat(),
                    "concurrency_at_request": current_concurrency
                }
                
        except asyncio.TimeoutError:
            return {
                "request_id": request_id,
                "error": "Request timeout",
                "success": False,
                "timestamp": datetime.fromtimestamp(time.time()).isoformat()
            }
        except Exception as e:
            return {
                "request_id": request_id,
                "error": str(e),
                "success": False,
                "timestamp": datetime.fromtimestamp(time.time()).isoformat()
            }

    async def worker(self, worker_id: int, results: List[Dict], stop_event: asyncio.Event):
        """Worker that makes requests until stopped"""
        request_count = 0
        start_time = time.time()
        
        while not stop_event.is_set():
            current_time = time.time()
            concurrency_at_time = self.calculate_concurrency_at_time(current_time)
            
            # Check if we should exceed max concurrency
            if concurrency_at_time > self.max_concurrency:
                await asyncio.sleep(0.1)
                continue
                
            request_result = await self.make_request_with_think_time(request_count)
            results.append(request_result)
            request_count += 1
            
            # Log progress every 50 requests
            if request_count % 50 == 0:
                logger.info(f"Worker {worker_id}: {request_count} requests completed")
                
            # Small delay between requests from same worker
            await asyncio.sleep(0.01)

    async def run_test(self, target_requests: int = 1000) -> TestResult:
        """Run optimized load test with gradual ramp-up"""
        
        # Create aiohttp session
        self.session = aiohttp.ClientSession()
        
        logger.info("Starting optimized load test")
        logger.info(f"Configuration: Ramp-up {self.ramp_up_duration}s, Max concurrency {self.max_concurrency}")
        logger.info(f"Target requests: {target_requests}")
        
        # Create shared data structures
        all_results = []
        stop_event = asyncio.Event()
        
        # Create workers (start with minimal concurrency)
        num_workers = min(20, self.max_concurrency)
        workers = []
        
        for i in range(num_workers):
            worker = asyncio.create_task(self.worker(i, all_results, stop_event))
            workers.append(worker)
        
        # Monitor concurrency and stop when target reached
        async def monitor_concurrency():
            last_log_time = time.time()
            while not stop_event.is_set():
                current_time = time.time()
                concurrency = self.calculate_concurrency_at_time(current_time)
                
                # Log concurrency status every 5 seconds
                if current_time - last_log_time >= 5:
                    elapsed = current_time - self.start_time
                    progress = min(elapsed / self.ramp_up_duration, 1.0)
                    logger.info(f"Concurrency: {concurrency}/{self.max_concurrency} | Progress: {progress*100:.1f}% | Elapsed: {elapsed:.1f}s")
                    last_log_time = current_time
                
                # Stop when target requests reached (approximately)
                if len(all_results) >= target_requests * 1.2:  # Allow some buffer
                    logger.info(f"Target requests reached ({len(all_results)}), stopping...")
                    stop_event.set()
                    break
                
                await asyncio.sleep(1)
        
        # Start monitor
        monitor_task = asyncio.create_task(monitor_concurrency())
        
        # Wait for test completion
        await stop_event.wait()
        
        # Stop monitoring
        monitor_task.cancel()
        
        # Stop workers
        for worker in workers:
            worker.cancel()
        
        # Wait for all tasks to complete
        await asyncio.gather(*workers, return_exceptions=True)
        
        # Close the session
        await self.session.close()
        self.session = None
        
        # Calculate statistics
        successful = [r for r in all_results if r.get("success", False)]
        failed = [r for r in all_results if not r.get("success", False)]
        
        duration = time.time() - self.start_time
        rps = len(all_results) / duration if duration > 0 else 0
        avg_response_time = duration / len(all_results) * 1000 if all_results else 0
        
        # Calculate max concurrency reached
        max_concurrency = 0
        for r in successful:
            if isinstance(r, dict) and "concurrency_at_request" in r:
                max_concurrency = max(max_concurrency, r["concurrency_at_request"])
        
        results = TestResult(
            total_requests=len(all_results),
            successful=len(successful),
            failed=len(failed),
            duration=round(duration, 2),
            rps=round(rps, 2),
            avg_response_time_ms=round(avg_response_time, 2),
            success_rate=round((len(successful) / len(all_results) * 100), 2) if all_results else 0,
            max_concurrency_reached=max_concurrency
        )
        
        # Save detailed results
        self.save_results(all_results, results)
        
        return results

    def save_results(self, all_results: List[Dict], test_result: TestResult):
        """Save detailed test results"""
        results_data = {
            "test_metadata": {
                "timestamp": datetime.now().isoformat(),
                "ramp_up_duration": self.ramp_up_duration,
                "max_concurrency": self.max_concurrency,
                "think_time_range": f"{self.think_time_min}-{self.think_time_max}s",
                "request_timeout": self.request_timeout
            },
            "test_results": test_result.__dict__,
            "successful_requests": [
                {
                    "id": r["request_id"],
                    "timestamp": r.get("timestamp"),
                    "status_code": r.get("status_code"),
                    "response": r.get("response")
                }
                for r in all_results if r.get("success")
            ],
            "failed_requests": [
                {
                    "id": r["request_id"],
                    "timestamp": r.get("timestamp"),
                    "error": r.get("error", "Unknown error")
                }
                for r in all_results if not r.get("success")
            ],
            "concurrency_timeline": [
                {
                    "timestamp": r.get("timestamp"),
                    "concurrency": r.get("concurrency_at_request", 0)
                }
                for r in all_results if "concurrency_at_request" in r
            ]
        }
        
        with open("optimized_load_test_results.json", "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to optimized_load_test_results.json")

async def main():
    """Main function to run the optimized load test"""
    
    # Create and run optimized load tester
    tester = OptimizedLoadTester("http://localhost:8000")
    
    try:
        results = await tester.run_test(target_requests=1000)
        
        # Print comprehensive results
        print("\n" + "="*60)
        print("OPTIMIZED LOAD TEST RESULTS")
        print("="*60)
        print(f"Total Requests: {results.total_requests}")
        print(f"Successful: {results.successful} ({results.success_rate}%)")
        print(f"Failed: {results.failed}")
        print(f"Duration: {results.duration} seconds")
        print(f"Requests per second: {results.rps}")
        print(f"Average response time: {results.avg_response_time_ms} ms")
        print(f"Max concurrency reached: {results.max_concurrency_reached}")
        print("="*60)
        
        if results.success_rate >= 70:
            print("EXCELLENT! Success rate above 70%")
        elif results.success_rate >= 50:
            print("GOOD! Success rate above 50%")
        elif results.success_rate >= 30:
            print("ACCEPTABLE! Success rate above 30%")
        else:
            print("POOR! Success rate below 30% - may need more optimization")
            
    except Exception as e:
        logger.error(f"Load test failed: {e}")
        print(f"Load test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
