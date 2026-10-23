#!/usr/bin/env python3
"""
Optimized Load Test for Desarrollo Créditos API
Implementation with proper ramp-up, concurrency limits, and realistic thinking time.
"""

import asyncio
import aiohttp
import time
import random
import json
from datetime import datetime
from typing import List, Dict, Any

# Test payload
TEST_PAYLOAD = {
    "tipo_id": "1",
    "numero_id": "1000000001",
    "primer_apellido": "Ficticio",
    "ocupacion": "Empleado",
    "tipo_contrato": "Indefinido",
    "fecha_nacimiento": "1990-05-15",
    "ingresos_mensuales": 5000000,
    "saldo_financiar": 10000000,
    "plazo": 36,
    "tasa": 2
}

class OptimizedLoadTester:
    def __init__(self):
        # Optimized configuration for realistic load testing
        self.target_requests = 1000
        self.max_concurrency = 50  # Safe limit to prevent overwhelming the server
        self.ramp_up_duration = 60  # Gradual increase over 60 seconds
        
        # Realistic thinking time (1-3 seconds) to simulate human behavior
        self.think_time_min = 1.0
        self.think_time_max = 3.0
        
        # Generous timeout to allow processing time
        self.request_timeout = 15
        
        # Statistics
        self.results = []
        self.start_time = None
        
    def calculate_concurrency_at_time(self, elapsed_time: float) -> int:
        """Calculate current concurrency based on ramp-up curve"""
        if elapsed_time <= 0:
            return 1  # Start with 1 concurrent request
            
        progress = min(elapsed_time / self.ramp_up_duration, 1.0)
        
        # Smooth ramp-up curve for realistic traffic
        if progress < 0.2:
            # Slow start: 1 → 5 users
            return max(1, int(1 + (progress * 4 / 0.2)))
        elif progress < 0.5:
            # Medium ramp: 5 → 20 users
            return int(5 + ((progress - 0.2) * 15 / 0.3))
        elif progress < 0.8:
            # Fast ramp: 20 → 50 users
            return int(20 + ((progress - 0.5) * 30 / 0.3))
        else:
            # Max load: 50 users
            return self.max_concurrency

    async def make_request(self, request_id: int, current_concurrency: int) -> Dict[str, Any]:
        """Make a single request with realistic thinking time"""
        # Random think time to simulate human behavior
        await asyncio.sleep(random.uniform(self.think_time_min, self.think_time_max))
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.request_timeout)) as session:
                async with session.post(
                    "http://localhost:8000/api/motor/evaluar",
                    json=TEST_PAYLOAD
                ) as response:
                    response_data = await response.json()
                    
                    return {
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat(),
                        "status_code": response.status,
                        "response": response_data,
                        "success": response.status == 200,
                        "think_time": random.uniform(self.think_time_min, self.think_time_max),
                        "concurrency_at_request": current_concurrency
                    }
                    
        except asyncio.TimeoutError:
            return {
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
                "error": "Timeout",
                "success": False
            }
        except Exception as e:
            return {
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "success": False
            }

    async def worker(self, worker_id: int, stop_event: asyncio.Event) -> List[Dict[str, Any]]:
        """Worker that makes requests until stopped"""
        worker_results = []
        request_count = 0
        
        while not stop_event.is_set():
            # Calculate current concurrency based on elapsed time
            elapsed = time.time() - self.start_time
            current_concurrency = self.calculate_concurrency_at_time(elapsed)
            
            # Check if we have too many active requests
            active_requests = len(worker_results) - sum(1 for r in worker_results if r.get("completed", False))
            if active_requests >= current_concurrency:
                await asyncio.sleep(0.1)
                continue
                
            # Make request
            request_result = await self.make_request(request_count, current_concurrency)
            request_result["completed"] = True
            request_result["worker_id"] = worker_id
            worker_results.append(request_result)
            
            request_count += 1
            
            # Log progress every 20 requests
            if request_count % 20 == 0:
                elapsed = time.time() - self.start_time
                current_concurrency = self.calculate_concurrency_at_time(elapsed)
                print(f"Worker {worker_id}: {request_count} requests, {current_concurrency} concurrent")
                
            # Small delay between requests from same worker
            await asyncio.sleep(random.uniform(0.1, 0.5))
        
        return worker_results

    async def monitor_and_stop(self, stop_event: asyncio.Event, target_requests: int):
        """Monitor progress and stop when target requests reached"""
        last_log_time = time.time()
        
        while not stop_event.is_set():
            elapsed = time.time() - self.start_time
            current_concurrency = self.calculate_concurrency_at_time(elapsed)
            total_requests_made = len([r for w in self.all_workers_results for r in w if r.get("completed", False)])
            
            # Log status every 10 seconds
            if elapsed - last_log_time >= 10:
                progress = min(elapsed / self.ramp_up_duration, 1.0)
                print(f"Progress: {progress*100:.1f}% | Concurrency: {current_concurrency} | "
                      f"Requests: {total_requests_made}/{target_requests} | "
                      f"Rate: {total_requests_made/elapsed:.1f} req/s")
                last_log_time = elapsed
            
            # Check if target reached
            if total_requests_made >= target_requests * 1.5:  # Allow some buffer
                print(f"Target requests reached ({total_requests_made}), stopping...")
                stop_event.set()
                break
            
            await asyncio.sleep(1)

    async def run_test(self) -> Dict[str, Any]:
        """Run the optimized load test"""
        print("Starting Optimized Load Test")
        print("="*60)
        print(f"Target Requests: {self.target_requests}")
        print(f"Max Concurrency: {self.max_concurrency}")
        print(f"Ramp-up Duration: {self.ramp_up_duration} seconds")
        print(f"Think Time: {self.think_time_min}-{self.think_time_max} seconds")
        print(f"Request Timeout: {self.request_timeout} seconds")
        print("="*60)
        
        self.start_time = time.time()
        self.all_workers_results = []
        
        # Create stop event
        stop_event = asyncio.Event()
        
        # Create monitor task
        monitor_task = asyncio.create_task(self.monitor_and_stop(stop_event, self.target_requests))
        
        # Create workers
        num_workers = min(20, self.max_concurrency)
        print(f"Creating {num_workers} workers...")
        
        worker_tasks = []
        for i in range(num_workers):
            worker_task = asyncio.create_task(self.worker(i, stop_event))
            worker_tasks.append(worker_task)
        
        # Wait for monitor to signal stop
        await stop_event.wait()
        
        # Stop monitor
        monitor_task.cancel()
        
        # Wait for workers to complete
        print("Stopping workers...")
        worker_results = await asyncio.gather(*worker_tasks, return_exceptions=True)
        
        # Collect all results
        self.all_workers_results = worker_results
        
        # Flatten all results
        all_results = []
        for worker_result in self.all_workers_results:
            if isinstance(worker_result, list):
                all_results.extend(worker_result)
        
        # Calculate statistics
        successful = [r for r in all_results if r.get("success", False)]
        failed = [r for r in all_results if not r.get("success", False)]
        
        duration = time.time() - self.start_time
        rps = len(all_results) / duration if duration > 0 else 0
        success_rate = (len(successful) / len(all_results) * 100) if all_results else 0
        
        # Calculate average concurrency
        avg_concurrency = sum(
            r.get("concurrency_at_request", 0) 
            for r in successful 
            if isinstance(r, dict) and "concurrency_at_request" in r
        ) / len(successful) if successful else 0
        
        results = {
            "total_requests": len(all_results),
            "successful": len(successful),
            "failed": len(failed),
            "duration": round(duration, 2),
            "rps": round(rps, 2),
            "success_rate": round(success_rate, 2),
            "avg_concurrency": round(avg_concurrency, 2),
            "sample_successful": successful[:5],
            "sample_failed": failed[:5]
        }
        
        # Save detailed results
        self.save_results(all_results, results)
        
        return results

    def save_results(self, all_results: List[Dict], test_results: Dict[str, Any]):
        """Save detailed test results"""
        results_data = {
            "test_metadata": {
                "timestamp": datetime.now().isoformat(),
                "target_requests": self.target_requests,
                "max_concurrency": self.max_concurrency,
                "ramp_up_duration": self.ramp_up_duration,
                "think_time_range": f"{self.think_time_min}-{self.think_time_max}s",
                "request_timeout": self.request_timeout
            },
            "test_results": test_results,
            "successful_requests": all_results[:50] if all_results else [],
            "failed_requests": [r for r in all_results if not r.get("success", False)][:10] if all_results else []
        }
        
        with open("optimized_load_test_final.json", "w") as f:
            json.dump(results_data, f, indent=2)
        
        print(f"Detailed results saved to optimized_load_test_final.json")

async def main():
    """Main function to run the optimized load test"""
    tester = OptimizedLoadTester()
    
    try:
        results = await tester.run_test()
        
        print("\n" + "="*60)
        print("OPTIMIZED LOAD TEST FINAL RESULTS")
        print("="*60)
        print(f"Total Requests: {results['total_requests']}")
        print(f"Successful: {results['successful']} ({results['success_rate']}%)")
        print(f"Failed: {results['failed']}")
        print(f"Duration: {results['duration']} seconds")
        print(f"Requests per second: {results['rps']}")
        print(f"Average Concurrency: {results['avg_concurrency']}")
        print("="*60)
        
        if results['success_rate'] >= 80:
            print("✅ EXCELLENT! Load test passed successfully")
            print("The API handled the realistic load pattern effectively.")
        elif results['success_rate'] >= 60:
            print("✅ GOOD! Load test performed well")
            print("The API can handle moderate load with the optimized settings.")
        elif results['success_rate'] >= 40:
            print("⚠️  ACCEPTABLE! Load test completed")
            print("Consider further optimization for production scenarios.")
        else:
            print("❌ POOR! Load test needs significant optimization")
            print("Review server capacity and error patterns in the detailed results.")
            
    except Exception as e:
        print(f"❌ Load test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
