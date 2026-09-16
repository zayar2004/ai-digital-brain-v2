# Acceptance Checklist

## ✅ Core System
- [x] Flask app starts without errors
- [x] Database initializes (19 tables)
- [x] Shops A1-A13 seeded
- [x] SUPER_ADMIN user created
- [x] All models importable
- [x] All services importable
- [x] All ingestion modules work
- [x] All AI modules work (optional when disabled)

## ✅ Authentication
- [x] Login page loads
- [x] Password hashing (pbkdf2:sha256)
- [x] Account lockout (5 attempts → 15 min)
- [x] Session management
- [x] Logout works
- [x] Generic auth errors (no user enumeration)

## ✅ Permissions
- [x] SUPER_ADMIN can do all
- [x] ADMIN can approve + manage users
- [x] EDITOR can create/edit
- [x] VIEWER read-only
- [x] Backend enforces (not just UI)

## ✅ Shop Isolation
- [x] Explicit shop in message wins
- [x] Verified Telegram mapping used when no explicit
- [x] No guess on ambiguous
- [x] Backend enforces (not AI)
- [x] Cross-shop leakage blocked

## ✅ Machine System
- [x] Create/edit/archive machines
- [x] Aliases (short/abbr/alt/keyword)
- [x] Search by name/model/unit/alias
- [x] Strict shop isolation

## ✅ Machine Codes
- [x] Excel import with shop selection
- [x] Flexible header detection
- [x] Preserve source (file/sheet/row)
- [x] Duplicate detection
- [x] Conflict detection
- [x] Approve flow
- [x] Search + copy button

## ✅ Knowledge
- [x] CRUD + approve + archive
- [x] Version history (never overwrite)
- [x] Restore previous version
- [x] Conflict detection (same unit+error_code)
- [x] Effective dates
- [x] Source traceability

## ✅ Error Knowledge / Cases
- [x] Separated (never promote case → rule)
- [x] Error code + name + symptoms + cause + solution
- [x] Approve flow
- [x] Excel import (specialized)
- [x] Auto-derive error code

## ✅ Ingestion
- [x] Excel (generic + error structure)
- [x] PDF text extraction
- [x] DOCX text extraction
- [x] TXT/MD
- [x] Image → OCR → candidates
- [x] Quick Teach (rule-based + AI optional)
- [x] Report parsing

## ✅ Search
- [x] Unified search (Knowledge + Machines + Codes + Errors + Cases)
- [x] Exact / prefix / contains / token
- [x] Score ranking
- [x] Strict shop isolation
- [x] Error code boost
- [x] Empty query safe

## ✅ AI (Optional)
- [x] Provider abstraction (OpenRouter/OpenAI/Gemini)
- [x] RAG pipeline
- [x] Grounding check (no hallucination)
- [x] Empty context → "not found" (no AI call)
- [x] Graceful degradation when disabled

## ✅ Tasks
- [x] Daily / Weekly / Monthly / Yearly / One-Time
- [x] Weekday, day-of-month, specific date
- [x] Task time
- [x] Priority
- [x] History (never overwrite)
- [x] Asia/Yangon timezone
- [x] NL parsing (Myanmar)

## ✅ Reports
- [x] Create from pasted text
- [x] Metrics extraction
- [x] Compare two reports
- [x] Never overwrite

## ✅ Files
- [x] Upload (safe filenames)
- [x] Category auto-detect
- [x] Path traversal blocked
- [x] Download (no path leak)
- [x] Delete (soft)

## ✅ Telegram Bot
- [x] /start /help /shop /today /tasks /errors /machine /search
- [x] Free text → direct DB (no AI)
- [x] Error code exact lookup
- [x] Error keyword → paginated list
- [x] Inline buttons (Next/Prev)
- [x] Callback query handling
- [x] allowed_updates includes callback_query
- [x] Shop resolution (explicit > verified > context)
- [x] Full record display (no AI rewrite)

## ✅ Users
- [x] Admin user CRUD
- [x] Role management
- [x] Disable (not delete)
- [x] Telegram user mapping
- [x] Link/Unlink/Verify/Block
- [x] Notification via bot

## ✅ Settings / Health / Backup
- [x] Settings (DB-backed)
- [x] Health check page
- [x] Backup create / download / restore
- [x] Safety backup before restore

## ✅ Audit
- [x] Log all critical actions
- [x] Never log secrets
- [x] Paginated viewer

## ✅ Security
- [x] Passwords hashed
- [x] CSRF protection
- [x] Shop scope in queries
- [x] Never trust client shop_id
- [x] Never trust Telegram username
- [x] Safe file uploads
- [x] No secret exposure
- [x] Audit logs (scrubbed)

## ✅ Tests
- [x] 42 unit tests pass
- [x] Test DB isolated (temp file)
- [x] Real DB unaffected by tests
- [x] Acceptance tests (Rules 92-98)

## ✅ PWA
- [x] manifest.json
- [x] Service worker
- [x] Icons 192/512
- [x] Meta tags

## ✅ Documentation
- [x] README.md
- [x] docs/DEPLOYMENT.md
- [x] docs/ARCHITECTURE.md
- [x] docs/CHECKLIST.md (this file)
- [x] docs/SUMMARY.md

## ⚠️ Known Limitations
- [ ] Google Drive sync (V9 future)
- [ ] Vector DB semantic search (V8 future)
- [ ] Voice input (V8 future)
- [ ] Multi-language UI (Myanmar only)
- [ ] Mobile app (PWA works)
