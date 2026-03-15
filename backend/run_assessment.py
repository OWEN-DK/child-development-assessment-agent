import httpx
import json
import sys
import time

# API Endpoint
url = "http://localhost:8000/assess"

# Sample Data - Complete with plan details to test the fix
payload = {
    "child_profile": {
        "name": "小明",
        "age": 6,
        "gender": "male",
        "issues": ["注意力不集中", "体弱多病", "怕高"],
        "interests": ["乐高", "画画"],
    },
    "proposed_plan": {
        "plan_name": "感统强化初级计划",
        "goals": ["提升前庭觉稳定性", "增强核心力量", "改善注意力"],
        "activities": [
            {
                "name": "直线行走",
                "duration_minutes": 10,
                "frequency_weekly": 3,
                "description": "在地上贴一条直线，脚跟抵脚尖行走，双手平举保持平衡",
                "intensity": "low",
            },
            {
                "name": "羊角球跳跃",
                "duration_minutes": 15,
                "frequency_weekly": 4,
                "description": "坐在羊角球上向前跳跃，保持身体直立",
                "intensity": "medium",
            },
            {
                "name": "拍球练习",
                "duration_minutes": 10,
                "frequency_weekly": 5,
                "description": "原地双手交替拍球，眼睛看球",
                "intensity": "medium",
            },
        ],
    },
    "history_context": [],
}


def run_test():
    print(f"🚀 Sending request to {url}...")
    print(
        f"📝 Payload preview: {payload['proposed_plan']['plan_name']} with {len(payload['proposed_plan']['activities'])} activities"
    )

    start_time = time.time()

    try:
        # Using httpx since it's already in project dependencies
        with httpx.Client(timeout=300.0) as client:
            response = client.post(url, json=payload)

        elapsed = time.time() - start_time

        if response.status_code == 200:
            print(f"\n✅ Success! Response received in {elapsed:.2f}s")
            result = response.json()

            # Extract and print score
            if "structured_data" in result and "score" in result["structured_data"]:
                score = result["structured_data"]["score"]
                print(f"🏆 Assessment Score: {score}")

            # Save the markdown report to a file
            if "markdown_content" in result:
                report_content = result["markdown_content"]
                output_file = "assessment_report.md"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(report_content)
                print(f"\n📄 Report saved to '{output_file}'")
                print("   You can open this file to see the full generated report.")
            else:
                print("\n⚠️ No markdown content in response")
                print(json.dumps(result, ensure_ascii=False, indent=2))

        else:
            print(f"\n❌ Error: Status {response.status_code}")
            print(response.text)

    except httpx.RequestError as e:
        print(f"\n❌ Connection error: {e}")
        print("💡 Hint: Make sure the backend server is running on port 8000.")
        print("   Run 'uv run python src/server.py' in the backend directory.")


if __name__ == "__main__":
    run_test()
