import httpx
import asyncio
import sys

async def verify_rate_limit():
    url = "http://localhost:8000/search"
    payload = {"query": "rate limit test", "limit": 1}

    print("Starting Rate Limit Verification...")

    success_count = 0
    blocked_count = 0

    async with httpx.AsyncClient() as client:
        for i in range(1, 11):
            try:
                response = await client.post(url, json=payload)
                print(f"Request {i}: Status {response.status_code}")

                if response.status_code == 202:
                    success_count += 1
                elif response.status_code == 429:
                    blocked_count += 1
            except Exception as e:
                print(f"Request {i} failed: {e}")

    print("\nResults:")
    print(f"Successful requests: {success_count}")
    print(f"Blocked requests (429): {blocked_count}")

    if success_count <= 5 and blocked_count >= 5:
        print("✅ Rate Limiting verified successfully!")
        sys.exit(0)
    else:
        print("❌ Rate Limiting verification failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify_rate_limit())
