import time

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
EMAIL = f"e2e-{int(time.time())}@example.com"
PASSWORD = "secmate-e2e-123"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 1. 注册
    page.goto(f"{BASE}/login")
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="立即注册").click()
    page.get_by_placeholder("you@example.com").fill(EMAIL)
    page.get_by_placeholder("至少 8 位").fill(PASSWORD)
    page.get_by_role("button", name="注册", exact=True).click()
    page.wait_for_url("**/analyze", timeout=20000)
    print("[1/6] 注册并跳转分析页 OK")

    # 2. header 显示配额徽章
    page.wait_for_selector("text=今日剩余", timeout=15000)
    print("[2/6] 配额徽章显示 OK")

    def run_analysis(wait_done: bool):
        page.goto(f"{BASE}/analyze")
        page.wait_for_load_state("networkidle")
        page.get_by_role("textbox").fill("什么是 SQL 注入？")
        page.get_by_role("button", name="开始分析").click()
        if wait_done:
            # 完成信号不能用免责声明文案——模型输出本身就以该文案结尾（提示词要求），
            # 会误判为已完成并在落库前导航走、中断请求。改为等待“停止生成”按钮卸载：
            # 它仅在 done/error 事件到达（done 事件在 record_analysis 落库之后发出）后消失。
            page.get_by_role("button", name="停止生成").wait_for(
                state="visible", timeout=15000
            )
            page.get_by_role("button", name="停止生成").wait_for(
                state="detached", timeout=120000
            )
        else:
            page.wait_for_timeout(4000)  # 配额在流开始前已扣减，中断也计数

    # 3. 前 2 次完整跑完（供历史断言），再快速消耗 3 次
    run_analysis(wait_done=True)
    run_analysis(wait_done=True)
    run_analysis(wait_done=False)
    run_analysis(wait_done=False)
    run_analysis(wait_done=False)
    print("[3/6] 5 次分析已消耗配额 OK")

    # 4. 第 6 次：出现升级引导卡片
    page.goto(f"{BASE}/analyze")
    page.wait_for_load_state("networkidle")
    page.get_by_role("textbox").fill("什么是 SQL 注入？")
    page.get_by_role("button", name="开始分析").click()
    page.wait_for_selector("text=今日免费额度已用完", timeout=15000)
    print("[4/6] 第 6 次触发升级卡片 OK")

    # 5. 历史列表与详情
    page.goto(f"{BASE}/history")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("a[href^='/history/']", timeout=15000)
    print("[5/6] 历史列表有记录 OK")
    page.locator("a[href^='/history/']").first.click()
    page.wait_for_selector("text=分析结果", timeout=15000)
    print("[6/6] 历史详情渲染 OK")

    # 6. 退出登录回匿名态
    page.goto(f"{BASE}/analyze")
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name=EMAIL).hover()
    page.get_by_role("button", name="退出登录").click()
    page.wait_for_selector("a[href='/login']", timeout=15000)
    print("[7/7] 退出登录回匿名态 OK")

    browser.close()
    print("E2E PASS")
