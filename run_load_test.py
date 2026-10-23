#!/usr/bin/env python3
"""
Load testing script for Desarrollo Créditos API.
Performs 1000 concurrent requests to the /api/motor/evaluar endpoint.
"""

import asyncio
import aiohttp
import json
import time
import subprocess
import sys
import os
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

def start_backend():
    """Start the FastAPI backend."""
    try:
        # Start the backend process
        backend_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--reload"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"Backend started with PID: {backend_process.pid}")
        return backend_process
    except Exception as e:
        print(f"Error starting backend: {e}")
        return None

def check_backend_health():
    """Check if backend is healthy."""
    try:
        import requests
        response = requests.get("http://localhost:8000/api/health", timeout=5)
        return response.status_code == 200
    except:
        return False

if __name__ == "__main__":
    print("Starting Desarrollo Créditos load test...")
    print(f"Target: 1000 concurrent requests to /api/motor/evaluar")
    
    # Start backend
    backend_process = start_backend()
    
    # Wait for backend to start
    print("Waiting for backend to start...")
    for i in range(30):  # Wait up to 30 seconds
        if check_backend_health():
            print("Backend is ready!")
            break
        time.sleep(1)
        if i % 5 == 0:
            print(f"Waiting... {i+1}/30 seconds")
    else:
        print("Backend failed to start within 30 seconds")
        if backend_process:
            backend_process.terminate()
        sys.exit(1)
    
    print("Starting load test...")
    
    try:
        # Run load test
        results = asyncio.run(run_load_test())
        
        # Save results to file for better reliability
        with open("load_test_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print("=== LOAD TEST RESULTS ===")
        print(f"Total Requests: {results['total_requests']}")
        print(f"Successful: {results['successful_requests']} ({results['success_rate']}%)")
        print(f"Failed: {results['failed_requests']}")
        print(f"Duration: {results['duration_seconds']} seconds")
        print(f"Requests per second: {results['requests_per_second']}")
        print(f"Average response time: {results['average_response_time_ms']} ms")
        
        # Save results to file
        with open("load_test_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print("\nLoad test completed successfully!")
        
    except KeyboardInterrupt:
        print("\nLoad test interrupted by user")
    except Exception as e:
        print(f"Error running load test: {e}")
    finally:
        # Stop backend
        if backend_process:
            print("Stopping backend...")
            backend_process.terminate()
            backend_process.wait(timeout=10)
            print("Backend stopped")
