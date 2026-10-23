#!/usr/bin/env python3
"""
Ultra-Simple Load Test for Desarrollo Créditos API
Basic test with realistic thinking time between requests.
"""

import aiohttp
import asyncio
import time
import random
import json
from datetime import datetime

# Simple test payload
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

async def make_request(session, request_id):
    """Make a single request with thinking time"""
    # Think time to simulate human behavior (1-3 seconds)
    await asyncio.sleep(random.uniform(1.0, 3.0))
    
    try:
        async with session.post(
            "http://localhost:8000/api/motor/evaluar",
            json=TEST_PAYLOAD,
            timeout=10
        ) as response:
            data = await response.json()
            
            return {
                "id": request_id,
                "status": response.status,
                "decision": data.get("decision"),
                "success": response.status == 200,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        return {
            "id": request_id,
            "status": "error",
            "error": str(e),
            "success": False,
            "timestamp": datetime.now().isoformat()
        }

async def run_load_test(total_requests=1000):
    """Run load test with controlled concurrency"""
    print(f"Starting load test: {total_requests} requests")
    print(f"Think time: 1-3 seconds between requests")
    
    results = []
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        # Create semaphore to limit concurrency to 30
        semaphore = asyncio.Semaphore(30)
        
        async def limited_request(request_id):
            async with semaphore:
                return await make_request(session, request_id)
        
        # Create all tasks
        tasks = [limited_request(i) for i in range(total_requests)]
        
        # Run tasks with asyncio.gather
        print("All requests queued, starting execution...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    duration = time.time() - start_time
    successful = [r for r in results if isinstance(r, dict) and r.get("success")]
    failed = [r for r in results if isinstance(r, dict) and not r.get("success")]
    
    # Calculate metrics
    rps = total_requests / duration if duration > 0 else 0
    
    print("\n" + "="*50)
    print("LOAD TEST RESULTS")
    print("="*50)
    print(f"Total Requests: {total_requests}")
    print(f"Successful: {len(successful)} ({len(successful)/total_requests*100:.1f}%)")
    print(f"Failed: {len(failed)}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Requests per second: {rps:.2f}")
    print(f"Average time per request: {duration/total_requests:.2f}s")
    print("="*50)
    
    if len(successful) / total_requests >= 0.7:
        print("✅ EXCELLENT! Load test passed successfully")
    elif len(successful) / total_requests >= 0.5:
        print("✅ GOOD! Load test performed well")
    elif len(successful) / total_requests >= 0.3:
        print("⚠️  ACCEPTABLE! Load test completed")
    else:
        print("❌ POOR! Load test needs optimization")
    
    # Save detailed results
    detailed_results = {
        "total_requests": total_requests,
        "successful": len(successful),
        "failed": len(failed),
        "duration": duration,
        "rps": rps,
        "success_rate": len(successful) / total_requests * 100,
        "successful_requests": successful[:10],
        "failed_requests": failed[:10]
    }
    
    with open("load_test_results.json", "w") as f:
        json.dump(detailed_results, f, indent=2)
    
    print(f"Results saved to load_test_results.json")

if __name__ == "__main__":
    asyncio.run(run_load_test())
