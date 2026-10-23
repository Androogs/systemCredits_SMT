#!/usr/bin/env python3
"""
Load testing script for Desarrollo Créditos API.
Performs 1000 concurrent requests to the /api/motor/evaluar endpoint.
"""

import asyncio
import aiohttp
import json
import time
import sys
from typing import Dict, Any

# Test payload based on tests.integration.conftest.PAYLOAD
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

async def make_request(session: aiohttp.ClientSession, request_id: int) -> Dict[str, Any]:
    """Make a single request to the API."""
    try:
        async with session.post(
            "http://localhost:8000/api/motor/evaluar",
            json=TEST_PAYLOAD,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            return {
                "request_id": request_id,
                "status_code": response.status,
                "response": await response.json(),
                "success": response.status == 200
            }
    except Exception as e:
        return {
            "request_id": request_id,
            "error": str(e),
            "success": False
        }

async def run_load_test(total_requests: int = 1000, concurrency: int = 100) -> Dict[str, Any]:
    """Run load test with specified concurrency."""
    start_time = time.time()
    results = []
    
    # Create semaphore to limit concurrency
    semaphore = asyncio.Semaphore(concurrency)
    
    async def limited_request(request_id: int):
        async with semaphore:
            return await make_request(session, request_id)
    
    async with aiohttp.ClientSession() as session:
        # Create all tasks
        tasks = [limited_request(i) for i in range(total_requests)]
        
        # Run all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Process results
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    failed = total_requests - successful
    
    # Calculate metrics
    rps = total_requests / duration if duration > 0 else 0
    avg_response_time = duration / total_requests if total_requests > 0 else 0
    
    # Safe print function
    def safe_print(text):
        try:
            print(text.encode('utf-8', errors='replace').decode('utf-8'))
        except:
            print(text)
    
    safe_print("=== LOAD TEST RESULTS ===")
    safe_print(f"Total Requests: {results['total_requests']}")
    safe_print(f"Successful: {results['successful_requests']} ({results['success_rate']}%)")
    safe_print(f"Failed: {results['failed_requests']}")
    safe_print(f"Duration: {results['duration_seconds']} seconds")
    safe_print(f"Requests per second: {results['requests_per_second']}")
    safe_print(f"Average response time: {results['average_response_time_ms']} ms")
    
    if results['failed_requests'] > 0:
        safe_print(f"\n⚠️  {results['failed_requests']} requests failed!")
        safe_print("Failed requests:")
        for result in results['sample_responses']:
            if not result.get('success'):
                safe_print(f"  - Request {result['request_id']}: {result.get('error', 'Unknown error')}")
    
    return {
        "total_requests": total_requests,
        "successful_requests": successful,
        "failed_requests": failed,
        "duration_seconds": round(duration, 2),
        "requests_per_second": round(rps, 2),
        "average_response_time_ms": round(avg_response_time * 1000, 2),
        "success_rate": round((successful / total_requests) * 100, 2) if total_requests > 0 else 0,
        "sample_responses": [r for r in results if isinstance(r, dict) and r.get("success")][:5]
    }

if __name__ == "__main__":
    import locale
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    
    print("Starting load test for Desarrollo Créditos API...")
    print(f"Target: 1000 concurrent requests to /api/motor/evaluar")
    print("Press Ctrl+C to stop\n")
    
    try:
        results = asyncio.run(run_load_test())
        
        # Save results to file for better reliability
        with open("load_test_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print("Load test results saved to load_test_results.json")
        
    except KeyboardInterrupt:
        print("\nLoad test interrupted by user")
    except Exception as e:
        print(f"Error running load test: {e}")
