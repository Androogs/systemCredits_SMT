#!/usr/bin/env python3
"""
Basic Load Test for Desarrollo Créditos API
Ultra-simple test that actually works.
"""

import aiohttp
import asyncio
import time
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

async def test_request(session, request_id):
    """Make a single request"""
    try:
        # Small delay to simulate human behavior
        await asyncio.sleep(1.0)
        
        async with session.post(
            "http://localhost:8000/api/motor/evaluar",
            json=TEST_PAYLOAD,
            timeout=10
        ) as response:
            data = await response.json()
            
            return {
                "id": request_id,
                "status": response.status,
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

async def main():
    """Main test function"""
    print("Starting basic load test...")
    print("This will make 10 requests to test the API")
    
    total_requests = 10
    successful = 0
    failed = 0
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        print("Creating tasks...")
        tasks = [test_request(session, i) for i in range(total_requests)]
        
        print("Running tasks...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, dict):
                if result.get("success"):
                    successful += 1
                else:
                    failed += 1
            else:
                failed += 1
    
    duration = time.time() - start_time
    success_rate = (successful / total_requests) * 100 if total_requests > 0 else 0
    
    print("\n" + "="*50)
    print("LOAD TEST RESULTS")
    print("="*50)
    print(f"Total Requests: {total_requests}")
    print(f"Successful: {successful} ({success_rate:.1f}%)")
    print(f"Failed: {failed}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Requests per second: {total_requests/duration:.2f}")
    print("="*50)
    
    # Save results
    with open("load_test_results.json", "w") as f:
        json.dump({
            "total_requests": total_requests,
            "successful": successful,
            "failed": failed,
            "duration": duration,
            "success_rate": success_rate
        }, f, indent=2)
    
    print("Results saved to load_test_results.json")

if __name__ == "__main__":
    asyncio.run(main())
