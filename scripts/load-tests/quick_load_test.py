#!/usr/bin/env python3
"""
Load test that also starts the backend if needed.
"""

import subprocess
import time
import sys
import os

# Start the backend
print("Starting backend...")
backend_process = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--reload"],
    cwd=os.path.dirname(os.path.abspath(__file__)),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Wait for backend to start
print("Waiting for backend to start...")
time.sleep(10)

# Check if backend is responding
try:
    import requests
    response = requests.get("http://localhost:8000/api/health", timeout=5)
    if response.status_code == 200:
        print("Backend is ready!")
        
        # Now run the basic load test
        import basic_load_test
        # We'll need to modify basic_load_test to use the running backend
        # For now, let me just run a simple test using aiohttp directly
        
        async def quick_test():
            import aiohttp
            import asyncio
            
            payload = {
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
            
            async with aiohttp.ClientSession() as session:
                tasks = []
                for i in range(5):  # Just 5 requests for quick test
                    task = asyncio.create_task(make_request(session, i, payload))
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
                failed = len(results) - successful
                
                print(f"\nQuick test results:")
                print(f"Successful: {successful}/5 ({successful/5*100:.1f}%)")
                print(f"Failed: {failed}/5")
                
                # Save results
                import json
                with open("quick_test_results.json", "w") as f:
                    json.dump({
                        "total": len(results),
                        "successful": successful,
                        "failed": failed,
                        "success_rate": successful/5*100
                    }, f, indent=2)
        
        async def make_request(session, request_id, payload):
            try:
                await asyncio.sleep(0.5)  # Small delay
                async with session.post("http://localhost:8000/api/motor/evaluar", json=payload, timeout=10) as response:
                    data = await response.json()
                    return {
                        "id": request_id,
                        "status": response.status,
                        "success": response.status == 200
                    }
            except Exception as e:
                return {
                    "id": request_id,
                    "status": "error",
                    "error": str(e),
                    "success": False
                }
        
        # Run the quick test
        import asyncio
        asyncio.run(quick_test())
        
    else:
        print("Backend health check failed")
except Exception as e:
    print(f"Error checking backend: {e}")

# Stop backend
print("Stopping backend...")
backend_process.terminate()
backend_process.wait()
