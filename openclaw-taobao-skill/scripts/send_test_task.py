"""
任务发送工具 - 向本地飞书模拟器发送测试任务
运行方式: python scripts/send_test_task.py
"""
import requests
import json
import sys


def send_task(
        keyword="索尼耳机",
        min_positive_rate=99,
        max_items=3,
        headful=True,
        task_id="test-task-001"
):
    """
    向本地飞书模拟器发送测试任务

    Args:
        keyword: 搜索关键词
        min_positive_rate: 最低好评率
        max_items: 最大商品数量
        headful: 是否显示浏览器窗口
        task_id: 任务ID
    """
    task_data = {
        "task_id": task_id,
        "keyword": keyword,
        "min_positive_rate": min_positive_rate,
        "max_items": max_items,
        "headful": headful
    }

    try:
        # 直接添加到任务队列（通过特殊接口）
        response = requests.post(
            "http://localhost:8080/api/add_task",
            json=task_data,
            timeout=5
        )

        if response.status_code == 200:
            print(f"✅ 任务发送成功!")
            print(f"   任务ID: {task_id}")
            print(f"   关键词: {keyword}")
            print(f"   好评率: >={min_positive_rate}%")
            print(f"   商品数: {max_items}")
            print(f"   浏览器: {'显示' if headful else '隐藏'}")
        else:
            print(f"❌ 任务发送失败: {response.text}")

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到飞书模拟器，请先运行:")
        print("   python scripts/feishu_mock_server.py")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    # 支持命令行参数
    if len(sys.argv) > 1:
        keyword = sys.argv[1] if len(sys.argv) > 1 else "索尼耳机"
        rate = float(sys.argv[2]) if len(sys.argv) > 2 else 99
        items = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    else:
        keyword = "索尼耳机"
        rate = 99
        items = 3

    send_task(
        keyword=keyword,
        min_positive_rate=rate,
        max_items=items
    )
