"""
Centralized Myanmar help text.

Each page key maps to:
    title: short heading
    body: full help (supports simple Markdown-ish line breaks)
    tips: list of quick tips
"""

HELP: dict[str, dict] = {
    "dashboard": {
        "title": "Dashboard အသုံးပြုနည်း",
        "body": (
            "ဒီစာမျက်နှာက သင့် AI Digital Brain ရဲ့ ခြုံငုံအခြေအနေကို ပြပါတယ်။\n"
            "• Shops ကတ်တွေက ဆိုင် A1–A13 အားလုံးကို ပြပါတယ်။\n"
            "• Recent Activity က နောက်ဆုံး လုပ်ဆောင်ချက် ၅ ခုကို ပြပါတယ်။\n"
            "• ဘေးဘက် Menu ကနေ Knowledge, Machines, Files စတာတွေ ဝင်လို့ရပါတယ်။"
        ),
        "tips": [
            "Sidebar ကို ☰ နှိပ်ပြီး ဖွင့်/ပိတ်လို့ရတယ်။",
            "Dark/Light mode ကို အောက်ဆုံး ခလုတ်နဲ့ ပြောင်းလို့ရတယ်။",
        ],
    },
    "shops": {
        "title": "Shops ကြည့်နည်း",
        "body": (
            "ဒီစာမျက်နှာမှာ ဆိုင် A1–A13 အားလုံးကို ပြပါတယ်။\n"
            "• ဆိုင်တစ်ခုချင်း ကို ကိုယ်စားပြုတဲ့ code နဲ့ ပြထားပါတယ်။\n"
            "• ဆိုင်အသစ် ထည့်ခြင်း/ဖျက်ခြင်း ကို SUPER_ADMIN သာ လုပ်နိုင်ပါတယ်။"
        ),
        "tips": ["ဆိုင်ကုဒ် ကို `A3` ပုံစံနဲ့ အမြဲ ရေးပါ။"],
    },
    "machines": {
        "title": "Machines အသုံးပြုနည်း",
        "body": (
            "Machine ဆိုတာ ဆိုင်တစ်ခုထဲက စက်/ဂိမ်း/ယူနစ် တစ်ခုကို ဆိုလိုပါတယ်။\n"
            "• `+ New` နဲ့ စက်အသစ် ထည့်ပါ။\n"
            "• ဆိုင် (Shop) ကို မဖြစ်မနေ ရွေးပါ။\n"
            "• Search မှာ စက်နာမည်၊ model၊ alias ရိုက်ပြီး ရှာပါ။\n"
            "• Alias ဆိုတာ စက်ကို တခြားနာမည်နဲ့ ခေါ်တဲ့အခါ ရှာလို့ရအောင် သိမ်းထားတာပါ။"
        ),
        "tips": [
            "Alias ဥပမာ: Crocodile Tycoon အတွက် Croc, CT, Croc Ty",
            "Search က ဆိုင်အတွင်းမှာပဲ ရှာတယ် — တခြားဆိုင်ကို ရောက်မလာဘူး။",
        ],
    },
    "machine_form": {
        "title": "Machine ဖန်တီး/ပြင်နည်း",
        "body": (
            "• Name က မဖြစ်မနေ လိုတယ်။ ဆိုင်တစ်ခုထဲမှာ name ထပ်မရှိရဘူး။\n"
            "• Model / Unit က optional ပါ။\n"
            "• Aliases ကို တစ်ကြောင်းတစ်ခု ရေးပါ (Enter နဲ့ ခွဲ)။\n"
            "• Edit လုပ်တဲ့အခါ Shop ကို ပြောင်းလို့မရပါ။"
        ),
        "tips": ["Alias တွေကို မျဉ်းကြောင်းတစ်ကြောင်းချင်း ရေးပါ။"],
    },
    "machine_detail": {
        "title": "Machine အသေးစိတ်",
        "body": (
            "• Machine ရဲ့ အချက်အလက်အားလုံး ပြထားပါတယ်။\n"
            "• Edit နဲ့ အချက်အလက် ပြင်လို့ရတယ်။\n"
            "• Archive က စက်ကို ဖျက်တာမဟုတ်ဘဲ ပြတိုက်ထဲ သိမ်းထားတာပါ — ပြန်ထုတ်လို့ရတယ်။\n"
            "• Aliases ကို ဒီစာမျက်နှာကနေ ထည့်/ဖျက် လုပ်လို့ရတယ်။"
        ),
        "tips": ["Alias အသစ်တစ်ခု ထည့်ပြီးရင် search မှာ ချက်ချင်း အလုပ်လုပ်တယ်။"],
    },
    "machine_codes": {
        "title": "Machine Codes အသုံးပြုနည်း",
        "body": (
            "Machine Code ဆိုတာ စက်တစ်ခုအတွက် သီးသန့် ကုဒ်နံပါတ်ပါ။\n"
            "• အပေါ်က filter မှာ Shop ကို ရွေးပါ — မဖြစ်မနေ။\n"
            "• Search မှာ code၊ machine၊ model၊ unit ရိုက်ရှာလို့ရတယ်။\n"
            "• 📋 ခလုတ်က code ကို Copy ဖြစ်စေတယ်။\n"
            "• PENDING ဆိုတာ review မလုပ်ရသေးတာ — Approve နှိပ်ပြီးမှ official ဖြစ်တယ်။"
        ),
        "tips": [
            "Strict Shop Isolation: A3 ရဲ့ code ကို A5 မှာ မပြတယ်။",
            "Import Excel ကနေ code အများကြီး တစ်ခါတည်း ထည့်လို့ရတယ်။",
        ],
    },
    "machine_code_import": {
        "title": "Excel Import လုပ်နည်း",
        "body": (
            "• Shop ကို မဖြစ်မနေ ရွေးပါ — Import ဖြစ်တဲ့ code အားလုံး အဲ့ဒီဆိုင်ပိုင်ဖြစ်မယ်။\n"
            "• Excel ဖိုင်မှာ header row တစ်ခု အနည်းဆုံး ရှိရမယ်။\n"
            "• Header နာမည်တွေ: Machine Name, Model, Unit, Machine Code, Alias\n"
            "• Upload ပြီးရင် Preview မှာ Valid/Invalid/Duplicate/Conflict တွေ စစ်ပါ။\n"
            "• Import နှိပ်ရင် PENDING အဖြစ် သိမ်းမယ် — Approve နှိပ်မှ official ဖြစ်မယ်။"
        ),
        "tips": [
            "Duplicate ဆိုတာ file ထဲမှာ ထပ်နေတဲ့ row",
            "Conflict ဆိုတာ code တူပြီး unit မတူတဲ့ row",
        ],
    },
    "knowledge": {
        "title": "Knowledge အသုံးပြုနည်း",
        "body": (
            "Knowledge ဆိုတာ ဆိုင်တစ်ခုအတွက် သိမ်းထားတဲ့ အချက်အလက်တွေပါ။\n"
            "• Status တွေ: DRAFT → PENDING → APPROVED → ARCHIVED\n"
            "• APPROVED ဖြစ်မှသာ AI ဖြေတဲ့အခါ သုံးတယ်။\n"
            "• Quick Teach က စာသားကနေ knowledge ဖန်တီးတာ။\n"
            "• Ingest က PDF/DOCX/Excel ကနေ ဖန်တီးတာ။"
        ),
        "tips": [
            "Approved မဖြစ်သေးတဲ့ knowledge ကို AI က မသုံးဘူး။",
            "Version တစ်ခုချင်း သိမ်းထားတဲ့အတွက် ပြန်ကြည့်လို့ရတယ်။",
        ],
    },
    "knowledge_detail": {
        "title": "Knowledge အသေးစိတ်",
        "body": (
            "• ဒီစာမျက်နှာမှာ knowledge ရဲ့ အချက်အလက်အားလုံး၊ version history ကို ပြပါတယ်။\n"
            "• Approve နှိပ်ရင် Status = APPROVED ဖြစ်ပြီး AI က သုံးနိုင်ပါပြီ။\n"
            "• Archive နှိပ်ရင် knowledge ကို ပြတိုက်ထဲ သိမ်းထားမယ် — ဖျက်တာမဟုတ်ဘူး။"
        ),
        "tips": ["Version history က ဘယ်သူ ဘယ်တုန်း ဘာပြင်ခဲ့လဲ ပြပါတယ်။"],
    },
    "teach_quick": {
        "title": "Quick Teach အသုံးပြုနည်း",
        "body": (
            "• ဆိုင်ကို ရွေးပါ။\n"
            "• စက်အကြောင်း သင်သိထားတာကို ရိုးရိုး စာသားနဲ့ paste လုပ်ပါ။\n"
            "• AI ORGANIZE နှိပ်ရင် System က machine/unit/error code တွေ ခွဲထုတ်ပေးမယ်။\n"
            "• Preview မှာ စစ်ပြီး Save နှိပ်ရင် PENDING အဖြစ် သိမ်းမယ်။\n"
            "• Approve လုပ်ရင် APPROVED ဖြစ်မယ်။"
        ),
        "tips": [
            "ဥပမာ: \"Carnival circus P3 Error 07 ပေါ်နေ၍ coin ခွက်တွင် coin ကုန်နေတာတွေ့ပြီး ပြန်ဖြည့်လိုက်တာ အဆင်ပြေသွားတယ်\"",
            "Machine Hint ထည့်ရင် AI က ပိုမှန်မှန် ခွဲထုတ်နိုင်တယ်။",
        ],
    },
    "errors": {
        "title": "Error Knowledge အသုံးပြုနည်း",
        "body": (
            "Error Knowledge ဆိုတာ တရားဝင် error troubleshooting rule တွေပါ။\n"
            "• Error Code (07)၊ Error Name၊ Symptoms၊ Cause၊ Check၊ Solution တွေ ထည့်ပါ။\n"
            "• Historical case မျိုးကို Error Case မှာ သီးသန့် ထည့်ပါ။"
        ),
        "tips": ["Error Knowledge က universal rule ၊ Error Case က specific incident ။"],
    },
    "error_cases": {
        "title": "Error Cases အသုံးပြုနည်း",
        "body": (
            "Error Case ဆိုတာ တကယ်ဖြစ်ခဲ့တဲ့ case တစ်ခုပါ။\n"
            "• Problem = Admin တင်ပြတဲ့ ပြဿနာ\n"
            "• Finding = စစ်ကြည့်တဲ့အခါ တွေ့တာ\n"
            "• Action Taken = လုပ်ခဲ့တဲ့ ပြုပြင်မှု\n"
            "• Result = ရလဒ်\n"
            "⚠️ Case တစ်ခုတည်းကနေ universal rule မဖန်တီးရဘူး။"
        ),
        "tips": ["AI က Case တွေကို \"ယခင် case\" အနေနဲ့ပဲ ကိုးကားတယ်။"],
    },
    "files": {
        "title": "Files အသုံးပြုနည်း",
        "body": (
            "• ဆိုင်တစ်ခုကို ရွေးပြီး ဖိုင် upload လုပ်လို့ရတယ်။\n"
            "• PDF၊ DOCX၊ XLSX၊ ပုံတွေ အားလုံး ရတယ်။\n"
            "• Upload လုပ်ရင် အလိုအလျောက် category ခွဲပေးတယ်။\n"
            "• ဖိုင်ကို Download ပြန်လုပ်လို့ရတယ်။\n"
            "• ဖိုင်အမည်တွေကို System က လုံခြုံတဲ့ နာမည်နဲ့ သိမ်းတယ် — မူရင်းနာမည်ကို မှတ်ထားတယ်။"
        ),
        "tips": ["ပုံတွေအတွက် preview ကို detail page မှာ မြင်ရတယ်။"],
    },
    "ingest": {
        "title": "Ingest Documents အသုံးပြုနည်း",
        "body": (
            "• PDF၊ DOCX၊ XLSX၊ TXT ဖိုင်တွေကို upload လုပ်ပါ။\n"
            "• System က စာသားတွေ ဖတ်ပြီး Knowledge candidates ဖန်တီးတယ်။\n"
            "• Candidate တစ်ခုချင်း စစ်ပြီး လိုချင်တာတွေ ရွေးပါ။\n"
            "• Save နှိပ်ရင် PENDING အဖြစ် သိမ်းမယ် — Approve နှိပ်မှ official ဖြစ်မယ်။"
        ),
        "tips": ["Scan PDF များအတွက် OCR လိုတယ် — PART 15 မှာ ထည့်မယ်။"],
    },
    "audit": {
        "title": "Audit Log ကြည့်နည်း",
        "body": (
            "• စနစ်ထဲမှာ လုပ်ဆောင်ခဲ့တဲ့ အရေးကြီးတဲ့ လုပ်ဆောင်ချက်အားလုံး ဒီမှာ ပြပါတယ်။\n"
            "• Action၊ လုပ်သူ၊ Entity၊ IP၊ အချိန် တွေ ပြပါတယ်။\n"
            "• Password၊ API key၊ Token တွေကို လုံခြုံရေးအရ မှတ်တမ်းမတင်ဘူး။"
        ),
        "tips": ["SUPER_ADMIN / ADMIN သာ ကြည့်နိုင်တယ်။"],
    },
    "search": {
        "title": "Search အသုံးပြုနည်း",
        "body": (
            "Knowledge၊ Machines၊ Machine Codes၊ Errors၊ Error Cases အားလုံးကို တစ်ခါတည်း ရှာပါတယ်။\n"
            "• Query ရိုက်ပါ — ဥပမာ: 'Carnival P3 error 07' ဒါမှမဟုတ် 'Crocodile CT'\n"
            "• Shop ကို ရွေးရင် အဲ့ဒီဆိုင်အတွင်းမှာပဲ ရှာတယ်။\n"
            "• Approved only = APPROVED status ဖြစ်တာတွေပဲ ပြမယ်။\n"
            "• Result တွေကို အမျိုးအစားအလိုက် အုပ်စုဖွဲ့ ပြပါတယ်။"
        ),
        "tips": [
            "Search result ရဲ့ score က မြင့်လေ ပိုကိုက်လေ။",
            "Machine Code တွေကို Copy ခလုတ်နဲ့ ချက်ချင်း ကူးလို့ရတယ်။",
        ],
    },
    "image_ingest": {
        "title": "Image → Knowledge အသုံးပြုနည်း",
        "body": (
            "• ဆိုင်ကို ရွေးပြီး ပုံ/screenshot upload လုပ်ပါ။\n"
            "• OCR ရနိုင်ရင် စာသား ဖတ်ပြီး Knowledge candidate ဖန်တီးမယ်။\n"
            "• Caption / Description ထည့်ရင် ပိုမှန်မှန် ခွဲထုတ်နိုင်တယ်။\n"
            "• Save နှိပ်ရင် PENDING အဖြစ် သိမ်းမယ်။"
        ),
        "tips": [
            "Tesseract install မရှိရင် OCR မလုပ်နိုင်ပါ။ (pkg install tesseract tesseract-lang)",
            "ပုံထဲမှာ machine name/error code တွေ ပါရင် auto-extract ဖြစ်တယ်။",
        ],
    },
    "ai_test": {
        "title": "AI Test Center အသုံးပြုနည်း",
        "body": (
            "AI က ဘယ်လို ဖြေနေလဲ ရှင်းရှင်းလင်းလင်း ကြည့်ဖို့ ဒီစာမျက်နှာကို သုံးပါ။\n"
            "• Question ရိုက်ပြီး Test AI နှိပ်ပါ။\n"
            "• Search Hits က deterministic search ရလဒ် (AI မပါဘဲ)။\n"
            "• Final Answer က AI ရဲ့ ဖြေချက်။\n"
            "• Grounding = OK ဆိုရင် AI က context ထဲကပဲ ဖြေတယ်။\n"
            "• Grounding = PROBLEMS ဆိုရင် AI က context မှာ မပါတဲ့ အချက်ထည့်ဖို့ ကြိုးစားတယ် — စစ်ပါ။"
        ),
        "tips": [
            "ဒီစာမျက်နှာက developer/debug အတွက် အဓိကပါ။",
            "Grounding Problems တွေ့ရင် AI output ကို မယုံပါနဲ့။",
        ],
    },
    "tasks": {
        "title": "Tasks အသုံးပြုနည်း",
        "body": (
            "Task ဆိုတာ ဆိုင်တစ်ခုအတွက် ပုံမှန် လုပ်ဆောင်ရမယ့် အလုပ်တွေပါ။\n"
            "• Frequency: နေ့စဉ် / အပတ်စဉ် / လစဉ် / နှစ်စဉ် / တစ်ခါတည်း\n"
            "• Natural language နဲ့ ရေးလို့ရတယ် — AI က ခွဲထုတ်ပေးမယ်။\n"
            "• Tabs: Today / Upcoming / Overdue / Completed / All\n"
            "• Task တစ်ခုကို Complete / Skip လုပ်လို့ရတယ်။"
        ),
        "tips": [
            "ဥပမာ: 'A3 Crocodile ကို တနင်္လာနေ့တိုင်း မနက် ၉ နာရီ စစ်မယ်'",
            "Task history ကို မဖျက်ဘူး — အားလုံး မှတ်ထားတယ်။",
        ],
    },
    "reports": {
        "title": "Reports အသုံးပြုနည်း",
        "body": (
            "Report ဆိုတာ ရက်စွဲတစ်ခုအတွက် လုပ်ငန်း metrics တွေပါ။\n"
            "• ရိုးရိုး စာသားနဲ့ paste လုပ်ပါ။\n"
            "• System က metric တွေကို extract လုပ်ပြီး preview ပြမယ်။\n"
            "• တူတဲ့ ရက်စွဲမှာ report ၂ ခု မထပ်ရဘူး။\n"
            "• Compare က report ၂ ခုကို နှိုင်းယှဉ်ပြမယ်။"
        ),
        "tips": [
            "ဥပမာ: '7/9/2026 Update\\nMachine 144\\nDaily Key 236'",
            "Report ဟောင်းတွေကို မဖျက်ဘူး — အားလုံး သိမ်းထားတယ်။",
        ],
    },
    "admin_users": {
        "title": "Admin Users အသုံးပြုနည်း",
        "body": (
            "Admin Users ဆိုတာ Website ကို ဝင်ရောက်တဲ့ အကောင့်တွေပါ။\n"
            "• SUPER_ADMIN — အားလုံး လုပ်နိုင်\n"
            "• ADMIN — operational data + knowledge approve\n"
            "• EDITOR — create/edit knowledge\n"
            "• VIEWER — ကြည့်ရုံပဲ\n"
            "• Disable လုပ်ရင် ဝင်လို့မရတော့ဘူး (ဖျက်တာမဟုတ်ဘူး)။"
        ),
        "tips": [
            "မိမိကိုယ်ကို Disable လုပ်လို့မရပါ။",
            "SUPER_ADMIN တစ်ခုတည်း ကျန်ရင် ဖျက်/ပိတ် လို့မရပါ။",
        ],
    },
    "telegram_users": {
        "title": "Telegram Users အသုံးပြုနည်း",
        "body": (
            "ဒီစာမျက်နှာက Telegram account တွေကို ဆိုင်တွေနဲ့ ချိတ်ဆက်ဖို့ ဖြစ်ပါတယ်။\n"
            "• User က bot ကို /start ပို့ရင် ဒီမှာ ပေါ်လာမယ်။\n"
            "• Manage ကို နှိပ် → Shop ရွေး → Link\n"
            "• Verified = ဒီ user ရဲ့ ဆိုင်ကို bot က သိနိုင်ပြီ\n"
            "• Block = bot ကို သုံးလို့မရတော့\n"
            "• Unlink = user→shop mapping ဖျက်"
        ),
        "tips": [
            "⚠️ Telegram username/name ကို မယုံပါနဲ့ — numeric ID ကိုပဲ ယုံပါ။",
            "User က A3 verified ဖြစ်ရင် 'Rampage code' ပို့ရင် A3 ထဲကပဲ ရှာမယ်။",
            "User က 'A5 CT code' ပို့ရင် A5 override လုပ်မယ်။",
        ],
    },
    "settings": {
        "title": "Settings အသုံးပြုနည်း",
        "body": (
            "System-wide configuration တွေကို ဒီမှာ ပြင်နိုင်ပါတယ်။\n"
            "• AI answer language / grounding strictness\n"
            "• Search results per page\n"
            "• Telegram notifications on/off\n"
            "• Backup auto-daily (future)\n"
            "• Site name / timezone"
        ),
        "tips": [
            "SUPER_ADMIN / ADMIN သာ Settings ပြင်နိုင်တယ်။",
            "Settings ပြောင်းရင် bot/page refresh လုပ်ပါ။",
        ],
    },
    "health": {
        "title": "System Health",
        "body": (
            "Database, AI provider, Telegram status တွေကို ကြည့်နိုင်တယ်။\n"
            "• Database: ok/error\n"
            "• AI: configured provider\n"
            "• Telegram: enabled/disabled\n"
            "• Records counts (Knowledge, Machines, Users...)"
        ),
        "tips": ["Error ရှိရင် Terminal log ကို ကြည့်ပါ။"],
    },
    "backup": {
        "title": "Backups အသုံးပြုနည်း",
        "body": (
            "Backup က DB + Uploads ကို zip ဖိုင်အဖြစ် သိမ်းတယ်။\n"
            "• Create: label ထည့်ပြီး manual backup\n"
            "• Download: ဖုန်းထဲ သိမ်း\n"
            "• Restore: backup ကနေ ပြန်တင် (safety backup auto)\n"
            "• Delete: backup ဖိုင် ဖျက်"
        ),
        "tips": [
            "Restore မလုပ်ခင် Server ကို ရပ်ထားပါ။",
            "Restore ပြီးရင် Server restart လုပ်ပါ။",
        ],
    },
    "analytics": {
        "title": "Analytics အသုံးပြုနည်း",
        "body": (
            "Web/Bot မှာ ရှာတဲ့ query တွေ၊ events တွေကို ကြည့်နိုင်ပါတယ်။\n"
            "• Top queries — အများဆုံး ရှာတာ\n"
            "• Top shops — ဆိုင်တိုင်း ရှာတဲ့ အရေအတွက်\n"
            "• Sources — Web / Telegram / API\n"
            "• Top Telegram users\n"
            "• Daily searches chart"
        ),
        "tips": ["Period ကို 1/7/14/30/90 days ရွေးလို့ရတယ်။"],
    },
    "broadcast": {
        "title": "Broadcast အသုံးပြုနည်း",
        "body": (
            "Admin က စာ ဒါမှမဟုတ် ပုံ ရိုက် → Verified Telegram users အားလုံး ဆီ ချက်ချင်း ရောက်ပါတယ်။\n"
            "• Message ရိုက်\n"
            "• Photo ရွေး (optional)\n"
            "• Filter Shop (optional) — ဆိုင်တစ်ခုရဲ့ users ပဲ\n"
            "• Send Now\n"
            "• Recipient တစ်ယောက်ချင်း ရောက်/မရောက် log မှတ်"
        ),
        "tips": [
            "⚠️ Verified users ကိုပဲ ပို့တယ်။ Unverified — မရောက်ဘူး။",
            "Photo ကို resize လုပ်ပြီး Telegram server ပေါ် တစ်ခါတည်း cache ဖြစ်တယ်။",
            "နောက် broadcast တွေမှာ photo ကို file_id နဲ့ ပြန် send — instant။",
        ],
    },
    "telegram_groups": {
        "title": "Telegram Groups အသုံးပြုနည်း",
        "body": (
            "Telegram Group (Topics enabled) မှာ Bot ကို သုံးလို့ရအောင် ချိတ်ဆက်ပါ။\n"
            "• Group → Message Link (t.me/c/.../...) → Web မှာ ထည့်\n"
            "• ဒါမှမဟုတ် — Group ထဲမှာ /setup ပို့\n"
            "• Allowed Topic IDs — Bot ဖြေမယ့် Topic\n"
            "• အခြား Topic တွေမှာ — Bot က မဖြေဘူး"
        ),
        "tips": [
            "Bot → Group Admin ထည့်ရမယ်",
            "🤖 AI Bot Topic — ဒီမှာပဲ Bot ဖြေမယ်",
        ],
    },
    "login": {
        "title": "Login ဝင်နည်း",
        "body": (
            "• Username နဲ့ Password ထည့်ပါ။\n"
            "• ၅ ခါ မှားရင် Account ကို ၁၅ မိနစ် ပိတ်မယ်။\n"
            "• Password မမှတ်မိရင် Administrator ကို ဆက်သွယ်ပါ။"
        ),
        "tips": ["Remember me ကို ဖုန်းတစ်လုံးတည်းမှာ သုံးရင် မလိုအပ်ပါ။"],
    },
}
