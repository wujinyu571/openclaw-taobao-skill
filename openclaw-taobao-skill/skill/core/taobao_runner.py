from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Callable
from uuid import uuid4

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from skill.config import Settings
from skill.core.parser import parse_positive_rate
from skill.models import ItemResult, RunResult, TaskPayload


class TaobaoRunner:
    def __init__(self, settings: Settings, logger: Callable[[str], None]) -> None:
        self.settings = settings
        self.logger = logger
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    async def run(self, payload: TaskPayload) -> RunResult:
        run_id = str(uuid4())
        screenshot_path = str(self.logs_dir / f"{run_id}.png")
        result = RunResult(
            run_id=run_id,
            task_id=payload.task_id,
            success=False,
            message="UNKNOWN_ERROR",
            artifacts={"screenshot": screenshot_path},
        )

        async with async_playwright() as p:
            headless = not payload.headful if payload.headful else self.settings.headless
            context, browser = await self._create_context(p, headless=headless)
            page = context.pages[0] if context.pages else await context.new_page()
            page.set_default_timeout(self.settings.browser_timeout_ms)
            try:
                await self._login(page)
                await self._save_session_state(context)

                # 执行搜索并获取最新的页面对象（可能是新标签页）
                page = await self._search(page, payload.keyword)

                # 关键：等待网络空闲和页面渲染，确保截图是完整的搜索结果
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)

                # 截取搜索结果页
                await page.screenshot(path=screenshot_path, full_page=True)
                self.logger(f"Search result screenshot saved to {screenshot_path}")

                items, matched_urls = await self._collect_items(page, payload.min_positive_rate, payload.max_items)
                if not items and await self._is_risk_control_page(page):
                    self.logger("Verification page detected after collect, wait manual and retry search once")
                    await self._wait_for_manual_verification(page, stage="after_collect")
                    page = await self._search(page, payload.keyword)
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(2000)
                    await page.screenshot(path=screenshot_path, full_page=True)
                    items, matched_urls = await self._collect_items(page, payload.min_positive_rate, payload.max_items)

                if not items:
                    result.message = "NO_MATCHED_ITEMS"
                    return result

                add_count = await self._add_to_cart(page, matched_urls)
                result.success = add_count > 0
                result.message = "OK" if result.success else "ADD_TO_CART_FAILED"
                result.matched_items = items
                result.added_to_cart_count = add_count
                return result
            except PlaywrightTimeoutError:
                result.message = "ACTION_TIMEOUT"
                # 超时也截一张图，方便看卡在哪了
                await page.screenshot(path=screenshot_path, full_page=True)
                return result
            except Exception as exc:  # noqa: BLE001
                self.logger(f"Unhandled error: {exc}")
                error_text = str(exc)
                result.message = error_text if error_text.startswith("LOGIN_FAILED") else "RUNNER_EXCEPTION"
                # 异常也截一张图
                await page.screenshot(path=screenshot_path, full_page=True)
                return result
            finally:
                # 这里不再重复截图，只负责清理资源
                await context.close()
                if browser is not None:
                    await browser.close()

    async def _login(self, page) -> None:
        self.logger("Open taobao home page")
        await page.goto("https://www.taobao.com/", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        if await self._is_logged_in(page):
            self.logger("Session is already logged in, skip login step")
            return
        self.logger("Try entering login page")

        login_candidates = [
            "text=亲，请登录",
            "text=登录",
            "a[href*='login']",
        ]
        for selector in login_candidates:
            locator = page.locator(selector).first
            if await locator.count() > 0:
                await locator.click()
                break
        await page.wait_for_timeout(1500)

        if self.settings.semi_auto_mode and not self.settings.auto_password_login:
            self.logger("Semi-auto mode enabled: please login and finish verification manually")
            await self._wait_for_manual_login(page)
            return

        username = self.settings.taobao_username
        password = self.settings.taobao_password
        if not username or not password:
            raise RuntimeError("TAOBAO_USERNAME or TAOBAO_PASSWORD is empty")

        user_inputs = ["input[name='fm-login-id']", "input#fm-login-id", "input[name='TPL_username']"]
        pass_inputs = ["input[name='fm-login-password']", "input#fm-login-password", "input[name='TPL_password']"]
        login_buttons = ["button[type='submit']", "text=登录", ".fm-button.fm-submit"]

        await self._fill_first_visible(page, user_inputs, username)
        await self._fill_first_visible(page, pass_inputs, password)
        await self._click_first_visible(page, login_buttons)

        await page.wait_for_timeout(4000)
        if await self._is_risk_control_page(page):
            self.logger("Risk control detected after password submit")
            await self._wait_for_manual_verification(page, stage="login")
            await self._wait_for_manual_login(page)
            return

        if not await self._is_logged_in(page):
            self.logger("Password login not confirmed, wait for manual QR login")
            await self._wait_for_manual_login(page)

    async def _search(self, page, keyword: str):
        if await self._is_risk_control_page(page):
            self.logger("Verification page detected before search")
            await self._wait_for_manual_verification(page, stage="before_search")
        self.logger(f"Search keyword: {keyword}")

        # 1. 准备监听新页面（因为淘宝搜索通常会在新标签页打开）
        context = page.context
        new_page_promise = context.wait_for_event("page")

        search_boxes = ["input[name='q']", "#q", "input[aria-label='搜索']"]
        search_buttons = [".btn-search", "button[type='submit']", "text=搜索"]

        await self._fill_first_visible(page, search_boxes, keyword)
        await self._click_first_visible(page, search_buttons)

        # 2. 等待新页面打开
        try:
            new_page = await asyncio.wait_for(new_page_promise, timeout=10.0)
            self.logger("New search tab detected, switching context...")
            page = new_page  # 关键：将 page 指针切换到新标签页
            await page.wait_for_load_state("domcontentloaded")
        except asyncio.TimeoutError:
            self.logger("No new tab opened, continuing on current page.")
            # 如果没有新标签页，则等待当前页面加载
            await page.wait_for_load_state("domcontentloaded")

        # 3. 增加等待时间确保商品列表渲染
        await page.wait_for_timeout(3000)

        if await self._is_risk_control_page(page):
            self.logger("Verification page detected after search submit")
            await self._wait_for_manual_verification(page, stage="after_search")

        # 4. 将处理好的 page 对象存回实例变量或返回给调用者
        # 由于 Python 的参数传递机制，直接赋值 page = new_page 不会改变 run 方法里的 page 引用
        # 所以我们需要一种方式让 run 方法知道页面变了。
        # 最简单的办法是：在 run 方法里重新获取最新的 page，或者让 _search 返回新的 page。
        # 这里我们采用返回新 page 的方式，需要修改 run 方法的调用逻辑。
        return page

    async def _collect_items(self, page, min_rate: float, max_items: int) -> tuple[list[ItemResult], list[str]]:
        self.logger(f"Collecting items by checking detail pages for positive rate >= {min_rate}")

        # 1. 滚动页面触发懒加载
        await page.mouse.wheel(0, 1000)
        await page.wait_for_timeout(1500)

        # 2. 在列表页抓取所有商品链接
        item_links = page.locator("a[href*='item.taobao.com'], a[href*='detail.tmall.com']")
        count = await item_links.count()
        self.logger(f"Found {count} item links on the search page.")

        picked: list[ItemResult] = []
        matched_urls: list[str] = []  # 新增：存储匹配商品的URL

        scan_limit = getattr(self.settings, 'max_scan_items', 20)
        scan_total = min(count, scan_limit)

        for idx in range(scan_total):
            if len(picked) >= max_items:
                break

            try:
                link_el = item_links.nth(idx)
                href = await link_el.get_attribute("href")
                title = await link_el.inner_text()

                if not href or not title.strip():
                    continue

                self.logger(f"Checking item {idx + 1}: {title.strip()[:30]}...")

                # 3. 在新标签页打开商品详情
                context = page.context
                new_page_promise = context.wait_for_event("page")
                await link_el.click(button="middle")

                detail_page = None
                try:
                    detail_page = await asyncio.wait_for(new_page_promise, timeout=10.0)
                    await detail_page.wait_for_load_state("domcontentloaded")
                    await detail_page.wait_for_timeout(1500)
                except Exception as e:
                    self.logger(f"Failed to open detail page: {e}")
                    if detail_page: await detail_page.close()
                    continue

                # 4. 在详情页提取好评率 (修复 body 报错)
                # 使用 evaluate 获取全文本比 inner_text 更快且更稳定
                try:
                    page_text = await detail_page.evaluate("() => document.body.innerText")
                except:
                    # 兜底方案
                    page_text = await detail_page.locator("body").inner_text()

                rate = parse_positive_rate(page_text)
                self.logger(f"Parsed rate for item {idx + 1}: {rate}")

                if rate is not None and rate >= min_rate:
                    # 在详情页重新提取纯净标题和价格
                    try:
                        detail_title = await detail_page.locator(
                            ".tb-main-title, .ItemTitle--title--eZ0i8").first.inner_text()
                    except:
                        detail_title = title.strip()

                    # 增强价格提取逻辑
                    price_val = await self._extract_price(detail_page)

                    picked.append(ItemResult(
                        title=detail_title.strip()[:100],
                        price=price_val,
                        positive_rate=rate
                    ))
                    matched_urls.append(href)
                    self.logger(f"✅ Matched! Rate: {rate}%")

                # 关闭详情页
                await detail_page.close()
                await page.bring_to_front()

            except Exception as e:
                self.logger(f"Error processing item {idx}: {e}")
                try:
                    await page.bring_to_front()
                except:
                    pass
                continue

        return picked, matched_urls

    async def _extract_price(self, page) -> str:
        """
        从商品详情页提取价格

        尝试多种选择器和策略，提高价格提取成功率
        """
        # 策略1：常见价格选择器
        price_selectors = [
            ".tm-price",  # 天猫价格
            ".Price--priceSign--XwYj3",  # 新版的Price组件
            "[class*='price']",  # 包含price的class
            ".g_price strong",  # 价格数字部分
            "#J_StrPriceModBox strong",  # 老版本价格容器
            "[data-spm='dprice'] strong",  # SPM标记的价格
            ".tb-rmb-num",  # 人民币符号后的数字
        ]

        for selector in price_selectors:
            try:
                price_el = page.locator(selector).first
                if await price_el.count() > 0:
                    price_text = await price_el.inner_text()
                    price_text = price_text.strip()

                    # 清理文本，只保留数字和小数点
                    import re
                    price_match = re.search(r'[\d.]+', price_text)
                    if price_match:
                        price_num = price_match.group()
                        # 判断是否有小数点
                        if '.' in price_num:
                            return f"¥{price_num}"
                        else:
                            return f"¥{price_num}.00"
            except:
                continue

        # 策略2：通过JavaScript直接查找价格元素
        try:
            price_via_js = await page.evaluate("""
                () => {
                    // 查找包含¥符号的元素
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        const text = el.textContent;
                        if (text && text.includes('¥') && text.match(/\\d+/)) {
                            // 排除一些明显不是价格的元素
                            if (!el.closest('script') && !el.closest('style')) {
                                const match = text.match(/¥\\s*([\\d.]+)/);
                                if (match) {
                                    return '¥' + match[1];
                                }
                            }
                        }
                    }
                    return null;
                }
            """)

            if price_via_js:
                return price_via_js
        except:
            pass

        # 策略3：从页面JSON数据中提取（淘宝通常会在<script>中嵌入商品数据）
        try:
            price_from_json = await page.evaluate("""
                () => {
                    // 尝试从全局变量中获取价格
                    if (window.H5Data && window.H5Data.item) {
                        return '¥' + window.H5Data.item.price;
                    }
                    if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.item) {
                        return '¥' + window.__INITIAL_STATE__.item.price;
                    }
                    return null;
                }
            """)

            if price_from_json:
                return price_from_json
        except:
            pass

        # 所有策略都失败
        return "未知价格"

    async def _add_to_cart(self, page, matched_urls: list[str]) -> int:
        self.logger(f"Try adding {len(matched_urls)} matched items to cart...")
        if await self._is_risk_control_page(page):
            self.logger("Verification page detected before add-to-cart")
            await self._wait_for_manual_verification(page, stage="before_add_to_cart")

        add_count = 0

        for idx, url in enumerate(matched_urls):
            try:
                # 修复：将相对URL转换为完整URL
                if url.startswith('//'):
                    full_url = 'https:' + url
                elif url.startswith('/'):
                    full_url = 'https://www.taobao.com' + url
                else:
                    full_url = url

                self.logger(f"Entering detail page for matched item {idx + 1}/{len(matched_urls)}...")
                self.logger(f"URL: {full_url}")

                # 1. 在新标签页打开匹配的商品
                context = page.context
                detail_page = await context.new_page()
                await detail_page.goto(full_url, wait_until="domcontentloaded", timeout=30000)
                await detail_page.wait_for_timeout(2000)

                # 2. 尝试点击加购按钮
                # 淘宝常见的加购按钮选择器集合
                cart_selectors = [
                    "#InitCartUrl",
                    ".tb-btn-cart",
                    "button[class*='cart']",
                    "text=加入购物车",
                    "[data-spm-click='gostr=/tbshop;locaid=d13']"
                ]

                clicked = False
                for selector in cart_selectors:
                    btn = detail_page.locator(selector).first
                    if await btn.count() > 0:
                        try:
                            await btn.scroll_into_view_if_needed()
                            await btn.click(timeout=3000)
                            self.logger("✅ Clicked add to cart button!")
                            clicked = True
                            break
                        except Exception as e:
                            self.logger(f"Click failed for selector {selector}: {e}")
                            continue

                if not clicked:
                    self.logger("Could not find any known 'Add to Cart' button selectors.")
                    # 截图调试
                    try:
                        await detail_page.screenshot(path=f"logs/debug_cart_fail_{idx}.png")
                    except:
                        pass

                # 3. 等待可能的弹窗（如规格选择）并尝试确认
                if clicked:
                    await detail_page.wait_for_timeout(1000)
                    # 简单的弹窗处理：如果出现了"确定"或"关闭"，点一下
                    confirm_btn = detail_page.locator("text=确定, text=关闭, .J_MakePoint").first
                    if await confirm_btn.count() > 0 and await confirm_btn.is_visible():
                        await confirm_btn.click()
                        self.logger("Handled popup confirmation.")

                add_count += 1 if clicked else 0

                # 4. 清理
                await detail_page.close()
                await page.bring_to_front()

            except Exception as e:
                self.logger(f"Error in add_to_cart for item {idx}: {e}")
                try:
                    await page.bring_to_front()
                except:
                    pass
                continue

        return add_count

    async def _fill_first_visible(self, page, selectors: list[str], value: str) -> None:
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() > 0:
                await locator.fill(value)
                return
        raise RuntimeError(f"Cannot find input from selectors: {selectors}")

    async def _click_first_visible(self, page, selectors: list[str]) -> None:
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() > 0:
                await locator.click()
                return
        raise RuntimeError(f"Cannot find clickable element from selectors: {selectors}")

    async def _safe_inner_text(self, node, selectors: list[str], default: str) -> str:
        for selector in selectors:
            loc = node.locator(selector).first
            if await loc.count() > 0:
                text = await loc.inner_text()
                if text.strip():
                    return text
        return default

    async def _is_risk_control_page(self, page) -> bool:
        url = page.url.lower()
        if any(keyword in url for keyword in ["captcha", "verify", "nocaptcha", "sec.taobao"]):
            return True

        risk_selectors = [
            "iframe[src*='captcha']",
            "iframe[src*='verify']",
            "text=请按住滑块",
            "text=请完成下方验证",
            "[id*='nc_']",
            ".nc_wrapper",
        ]
        for selector in risk_selectors:
            if await self._is_visible(page, selector):
                return True

        content = await page.content()
        return any(keyword in content for keyword in ["验证码", "安全验证", "短信验证", "滑块", "请完成验证"])

    async def _is_logged_in(self, page) -> bool:
        url = page.url.lower()
        if "login.taobao.com" in url:
            return False
        negative_locators = [
            "text=亲，请登录",
            "text=免费注册",
            "a[href*='login.taobao.com']",
        ]
        for selector in negative_locators:
            if await self._is_visible(page, selector):
                return False

        positive_locators = [
            "text=我的淘宝",
            "text=已买到的宝贝",
            "a[href*='member']",
            "text=退出",
        ]
        for selector in positive_locators:
            if await self._is_visible(page, selector):
                return True
        # Fallback for pages that do not expose obvious member labels after QR login.
        if await self._is_visible(page, "input[name='q']"):
            return True
        return False

    async def _is_visible(self, page, selector: str) -> bool:
        locator = page.locator(selector).first
        if await locator.count() == 0:
            return False
        try:
            return await locator.is_visible()
        except Exception:  # noqa: BLE001
            return False

    async def _wait_for_manual_login(self, page) -> None:
        timeout_sec = max(30, self.settings.manual_login_timeout_sec)
        self.logger(f"Please complete QR login manually within {timeout_sec} seconds")
        elapsed = 0
        while elapsed < timeout_sec:
            if await self._is_logged_in(page):
                self.logger("Manual login confirmed")
                return
            await page.wait_for_timeout(2000)
            elapsed += 2
        raise RuntimeError("LOGIN_FAILED_RISK_CONTROL")

    async def _wait_for_manual_verification(self, page, stage: str) -> None:
        timeout_sec = max(30, self.settings.manual_login_timeout_sec)
        elapsed = 0
        self.logger(
            f"Manual verification required at stage={stage}. "
            f"Please complete slider/captcha in {timeout_sec} seconds"
        )
        while elapsed < timeout_sec:
            if not await self._is_risk_control_page(page):
                self.logger("Manual verification confirmed")
                # 增加随机等待时间，模拟人类操作间隔
                import random
                wait_time = random.uniform(2, 5)
                if self.settings.manual_verify_gate:
                    await self._wait_for_ready_after_verification(page, stage=stage)
                return
            await page.wait_for_timeout(2000)
            elapsed += 2
            if elapsed % 10 == 0:
                remaining = max(0, timeout_sec - elapsed)
                self.logger(f"Waiting manual verification... remaining={remaining}s")
        raise RuntimeError("LOGIN_FAILED_RISK_CONTROL")

    async def _wait_for_ready_after_verification(self, page, stage: str) -> None:
        timeout_sec = max(30, self.settings.manual_verify_ready_timeout_sec)
        elapsed = 0
        self.logger(
            f"Manual verify gate enabled at stage={stage}. "
            f"Please ensure page is ready for next step within {timeout_sec} seconds"
        )
        while elapsed < timeout_sec:
            if await self._is_ready_after_verification(page):
                self.logger(f"Manual verify gate passed at stage={stage}")
                return
            await page.wait_for_timeout(2000)
            elapsed += 2
            if elapsed % 10 == 0:
                self.logger(f"Waiting page ready after verification... remaining={max(0, timeout_sec - elapsed)}s")
        raise RuntimeError("LOGIN_FAILED_RISK_CONTROL")

    async def _is_ready_after_verification(self, page) -> bool:
        if await self._is_risk_control_page(page):
            return False
        url = page.url.lower()
        if "login.taobao.com" in url:
            return False
        if any(part in url for part in ["s.taobao.com/search", "s.taobao.com"]):
            return True
        if await self._is_visible(page, "input[name='q']"):
            return True
        return False

    async def _create_context(self, playwright, headless: bool):
        channel = self.settings.browser_channel or None
        if self.settings.use_persistent_context:
            user_data_dir = Path(self.settings.browser_user_data_dir)
            user_data_dir.mkdir(parents=True, exist_ok=True)
            self.logger(f"Using persistent browser profile: {user_data_dir}")
            launch_options = {
                "headless": headless,
                "channel": channel,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--window-size=1920,1080"  # 固定窗口大小，防止布局变化触发风控
                ]
            }
            launch_options = {k: v for k, v in launch_options.items() if v is not None}
            context = await playwright.chromium.launch_persistent_context(str(user_data_dir), **launch_options)

            # 注入脚本隐藏 webdriver 属性
            await context.add_init_script("""
                            Object.defineProperty(navigator, 'webdriver', {
                                get: () => undefined
                            });
                            window.navigator.chrome = {
                                runtime: {},
                            };
                            Object.defineProperty(navigator, 'plugins', {
                                get: () => [1, 2, 3, 4, 5],
                            });
                        """)

            return context, None

        launch_options = {
            "headless": headless,
            "channel": channel,
        }
        launch_options = {k: v for k, v in launch_options.items() if v is not None}
        browser = await playwright.chromium.launch(**launch_options)
        context_options = self._build_context_options()
        context = await browser.new_context(**context_options)
        return context, browser

    def _build_context_options(self) -> dict:
        options: dict = {}
        if self.settings.persistent_session_enabled:
            state_path = Path(self.settings.session_state_path)
            if state_path.exists():
                self.logger(f"Load session state from {state_path}")
                options["storage_state"] = str(state_path)
        return options

    async def _save_session_state(self, context) -> None:
        if not self.settings.persistent_session_enabled:
            return
        state_path = Path(self.settings.session_state_path)
        await context.storage_state(path=str(state_path))
        self.logger(f"Session state saved to {state_path}")
