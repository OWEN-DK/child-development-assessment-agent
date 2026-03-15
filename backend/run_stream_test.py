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
    "is_streaming": True,
}


def run_stream_test():
    print(f"🚀 Sending STREAMING request to {url}...")
    print(
        f"📝 Payload preview: {payload['proposed_plan']['plan_name']} (Streaming Mode)"
    )

    start_time = time.time()
    full_content = ""

    try:
        # Using httpx since it's already in project dependencies
        with httpx.Client(timeout=300.0) as client:
            # Note: httpx handles streaming with stream()
            with client.stream("POST", url, json=payload) as response:
                print(f"✅ Connection established in {time.time() - start_time:.2f}s")

                if response.status_code != 200:
                    print(f"❌ Error: Status {response.status_code}")
                    print(response.read().decode())
                    return

                print("\n--- Streaming Output ---")

                for line in response.iter_lines():
                    if not line:
                        continue

                    line_text = line

                    if line_text.startswith("event:"):
                        event_type = line_text.replace("event: ", "").strip()
                        # print(f"Event: {event_type}")
                    elif line_text.startswith("data:"):
                        data_str = line_text.replace("data: ", "").strip()
                        if data_str == "[DONE]":
                            print("\n--- Stream Complete ---")
                            break

                        try:
                            data = json.loads(data_str)

                            if isinstance(data, dict) and "score" in data:
                                print(f"\n📊 Metadata Received: Score {data['score']}")
                            else:
                                # It's a text chunk
                                print(data, end="", flush=True)
                                full_content += data
                        except json.JSONDecodeError:
                            print(f"\nWarning: Could not decode JSON: {data_str}")

        elapsed = time.time() - start_time
        print(f"\n\n⏱️ Total time: {elapsed:.2f}s")

        # Save the markdown report to a file
        if full_content:
            output_file = "assessment_report_stream.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(full_content)
            print(f"\n📄 Full Report saved to '{output_file}'")

    except httpx.RequestError as e:
        print(f"\n❌ Connection error: {e}")
        print("💡 Hint: Make sure the backend server is running on port 8000.")


if __name__ == "__main__":
    run_stream_test()
