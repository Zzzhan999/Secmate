"""套餐配置：配额上限与定价页数据（/api/v1/plans 单一数据源）。"""

PLAN_LIMITS = {"free": 5, "pro": 200}

PRICING_PLANS = [
    {
        "id": "free",
        "name": "Free",
        "price": 0,
        "price_unit": "永久免费",
        "description": "入门学习，无需注册",
        "features": ["每日 5 次完整分析", "六类输入自动识别", "流式 Markdown + 代码高亮", "匿名使用"],
        "highlighted": False,
        "cta_text": "当前方案",
        "coming_soon": False,
    },
    {
        "id": "pro_monthly",
        "name": "Pro 月付",
        "price": 19,
        "price_unit": "元/月",
        "description": "备考冲刺、高频练习",
        "features": ["每日 200 次分析上限", "完整分析历史记录", "更强模型优先队列", "学习笔记整理（阶段5）"],
        "highlighted": True,
        "cta_text": "即将上线",
        "coming_soon": True,
    },
    {
        "id": "pro_yearly",
        "name": "Pro 年付",
        "price": 168,
        "price_unit": "元/年（省 60 元）",
        "description": "长期学习最划算",
        "features": ["含 Pro 月付全部权益", "年付优惠价", "3 天免费试用（后续开放）"],
        "highlighted": False,
        "cta_text": "即将上线",
        "coming_soon": True,
    },
    {
        "id": "pro_student",
        "name": "学生 Pro",
        "price": 9.9,
        "price_unit": "元/月",
        "description": "在校学生专属",
        "features": ["含 Pro 月付全部权益", "edu 邮箱验证（后续开放）"],
        "highlighted": False,
        "cta_text": "即将上线",
        "coming_soon": True,
    },
]
