"""
Admin web routes.

PART 7: Dashboard, Shops, Audit, Machines (list/create/edit/detail/alias).
"""

from __future__ import annotations

from flask import (
    Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.models import AuditLog, ErrorCase, ErrorKnowledge, Knowledge, KnowledgeStatus, Machine, MachineAlias, MachineCode, MachineCodeSource, MediaCategory, MediaFile, Shop, Task, TaskHistory, TelegramUser, TelegramUserShop, User, WorkReport
from app.models.user import Role
from app.security import permissions as P
from app.security.forms_helpers import fint, flines, ftext
from app.services import audit_service
from app.services import error_service as ES  # noqa: E402
from app.services import machine_service
from app.services.shop_service import get_shop_by_code, list_shops

admin_bp = Blueprint("admin", __name__)


def _require(permission: str):
    if not current_user.is_authenticated:
        abort(401)
    if not P.has_permission(current_user.role, permission):
        abort(403)


# ================================================================
# Dashboard
# ================================================================
@admin_bp.route("/")
@login_required
def dashboard():
    _require(P.DASHBOARD_VIEW)

    from app.models import (
        ErrorCase, ErrorKnowledge, Knowledge, Machine, MachineCode,
        Task, TelegramUser,
    )
    from app.models.base import utcnow
    from datetime import date

    shops = list_shops()
    recent_audit = AuditLog.query.order_by(AuditLog.id.desc()).limit(5).all()

    # ==== Counts ====
    counts = {
        "knowledge": Knowledge.query.filter_by(is_deleted=False).count(),
        "errors": ErrorKnowledge.query.filter_by(is_deleted=False).count(),
        "cases": ErrorCase.query.filter_by(is_deleted=False).count(),
        "machines": Machine.query.filter_by(is_deleted=False).count(),
        "codes": MachineCode.query.count(),
        "tasks": Task.query.filter_by(is_deleted=False).count(),
        "telegram_users": TelegramUser.query.filter_by(is_deleted=False).count(),
    }

    # ==== Action items ====
    action_items = []

    pending_kn = Knowledge.query.filter_by(status="PENDING", is_deleted=False).count()
    if pending_kn:
        action_items.append({
            "icon": "📖",
            "title": f"Pending Knowledge: {pending_kn}",
            "hint": "Approve လုပ်ရန် လိုတယ်",
            "url": url_for("admin.knowledge_list", status="PENDING"),
        })

    pending_err = ErrorKnowledge.query.filter_by(status="PENDING", is_deleted=False).count()
    if pending_err:
        action_items.append({
            "icon": "⚠️",
            "title": f"Pending Errors: {pending_err}",
            "hint": "Approve လုပ်ရန် လိုတယ်",
            "url": url_for("admin.errors_list", status="PENDING"),
        })

    # Open tasks
    open_tasks = Task.query.filter(
        Task.is_deleted.is_(False),
        Task.status.in_(("PENDING", "IN_PROGRESS")),
    ).count()
    if open_tasks:
        action_items.append({
            "icon": "📋",
            "title": f"Open Tasks: {open_tasks}",
            "hint": "ဒီနေ့ စစ်ရန်",
            "url": url_for("admin.tasks_list", tab="today"),
        })

    # ==== Health ====
    health = {"database": "ok", "ai": None, "telegram": None, "backup_ago": None}
    try:
        from sqlalchemy import text
        db.session.execute(text("SELECT 1"))
    except Exception:
        health["database"] = "error"

    try:
        from app.ai.provider import is_configured as ai_ok, provider_name
        if ai_ok():
            health["ai"] = provider_name()
    except Exception:
        pass

    from app.config import Config
    if Config.TELEGRAM_BOT_TOKEN:
        health["telegram"] = "ready"

    # Backup age
    try:
        import os
        backup_dir = os.path.join(app_root_path, "backups") if False else "backups"
        from pathlib import Path as _P
        bd = _P("backups")
        if bd.is_dir():
            zips = sorted(bd.glob("adb_full_*.zip"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
            if zips:
                age_sec = (utcnow().timestamp() - zips[0].stat().st_mtime)
                h = int(age_sec // 3600)
                if h < 1:
                    health["backup_ago"] = "just now"
                elif h < 24:
                    health["backup_ago"] = f"{h}h ago"
                else:
                    health["backup_ago"] = f"{h // 24}d ago"
    except Exception:
        pass

    return render_template(
        "admin/dashboard.html",
        user=current_user,
        shops=shops,
        recent_audit=recent_audit,
        counts=counts,
        action_items=action_items,
        health=health,
        today=date.today().isoformat(),
    )


@admin_bp.route("/shops/new", methods=["GET", "POST"])
@login_required
def shop_new():
    _require(P.SETTINGS_EDIT)
    from app.services import shop_service as SS

    if request.method == "POST":
        code = ftext("code", max_len=16)
        name = ftext("name", max_len=255)
        description = ftext("description", max_len=2000)
        is_active = bool(request.form.get("is_active"))

        try:
            shop = SS.create_shop(
                code=code,
                name=name or code,
                description=description or None,
                is_active=is_active,
            )
            audit_service.log(
                "shop.create",
                entity_type="shop",
                entity_id=shop.id,
                details={"code": shop.code, "name": shop.name},
            )
            flash(f"✓ ဆိုင် {shop.code} ဖန်တီးပြီးပါပြီ", "success")
            return redirect(url_for("admin.shops_list"))
        except ValueError as e:
            flash(str(e), "error")
            return render_template(
                "admin/shop_form.html",
                mode="new",
                form_data=request.form,
            )

    # GET
    return render_template(
        "admin/shop_form.html",
        mode="new",
        form_data={},
    )


@admin_bp.route("/shops")
@login_required
def shops_list():
    _require(P.SHOP_VIEW)
    from app.services import shop_service as SS
    shops = list_shops()
    stats = SS.shop_stats_bulk()
    return render_template("admin/shops.html", shops=shops, stats=stats)


@admin_bp.route("/shops/<code>")
@login_required
def shop_detail(code: str):
    _require(P.SHOP_VIEW)
    from app.services import shop_service as SS
    from app.services import media_service as MS
    shop = get_shop_by_code(code)
    if not shop:
        abort(404)
    stats = SS.shop_stats(shop.id)
    recent = (
        AuditLog.query.filter_by(shop_id=shop.id)
        .order_by(AuditLog.id.desc()).limit(10).all()
    )
    # ★ Shop files (MediaFile)
    shop_files = MS.list_media(shop_id=shop.id, limit=100)

    # ★ Machine Code Sources (Excel)
    machine_sources = MachineCodeSource.query.filter_by(
        shop_id=shop.id
    ).order_by(MachineCodeSource.id.desc()).limit(50).all()

    return render_template(
        "admin/shop_detail.html",
        shop=shop, stats=stats, recent=recent,
        shop_files=shop_files,
        machine_sources=machine_sources,
    )


@admin_bp.route("/shops/<code>/edit", methods=["POST"])
@login_required
def shop_edit(code: str):
    _require(P.SHOP_MANAGE)
    shop = get_shop_by_code(code)
    if not shop:
        abort(404)

    name = ftext("name", max_len=255) or None
    description = ftext("description", max_len=2000) or None

    # ★ Code never changes — only name/description
    shop.name = (name or shop.code).strip()
    shop.description = description

    db.session.commit()
    audit_service.log(
        "shop.edit", entity_type="shop",
        entity_id=shop.id, shop_id=shop.id,
        details={"name": shop.name},
    )
    flash(f"Shop {shop.code} အချက်အလက် ပြင်ပြီးပါပြီ။", "success")
    return redirect(url_for("admin.shop_detail", code=shop.code))


@admin_bp.route("/audit")
@login_required
def audit_list():
    _require(P.AUDIT_VIEW)
    page = request.args.get("page", type=int, default=1)
    pagination = (
        AuditLog.query.order_by(AuditLog.id.desc())
        .paginate(page=page, per_page=50, error_out=False)
    )
    return render_template("admin/audit.html", pagination=pagination)


# ================================================================
# Machines
# ================================================================
@admin_bp.route("/machines")
@login_required
def machines_list():
    _require(P.MACHINE_VIEW)

    shop_code = request.args.get("shop", "").strip().upper() or None
    q = request.args.get("q", "").strip()

    shop = get_shop_by_code(shop_code) if shop_code else None
    shop_id = shop.id if shop else None

    if q and shop_id:
        machines = machine_service.search_machines_in_shop(shop_id, q)
    else:
        machines = machine_service.list_machines(shop_id=shop_id, only_active=False)

    return render_template(
        "admin/machines.html",
        machines=machines,
        shops=list_shops(),
        current_shop=shop_code or "",
        q=q,
    )


@admin_bp.route("/machines/new", methods=["GET", "POST"])
@login_required
def machine_new():
    _require(P.MACHINE_CREATE)

    if request.method == "POST":
        shop_code = ftext("shop", max_len=16)
        name = ftext("name", max_len=255)
        model = ftext("model", max_len=128)
        unit = ftext("unit", max_len=64)
        description = ftext("description", max_len=2000)
        aliases = flines("aliases", max_lines=50)

        shop = get_shop_by_code(shop_code)
        if not shop:
            flash("ဆိုင်ကုဒ် မမှန်ကန်ပါ။", "error")
            return render_template("admin/machine_form.html", mode="new",
                                   shops=list_shops(), form_data=request.form)

        try:
            m = machine_service.create_machine(
                shop_id=shop.id, name=name, model=model, unit=unit,
                description=description, aliases=aliases,
            )
        except ValueError as e:
            flash(str(e), "error")
            return render_template("admin/machine_form.html", mode="new",
                                   shops=list_shops(), form_data=request.form)

        audit_service.log(
            "machine.create", entity_type="machine", entity_id=m.id,
            shop_id=m.shop_id, details={"name": m.name},
        )
        flash(f"Machine '{m.name}' ဖန်တီးပြီးပါပြီ။", "success")
        return redirect(url_for("admin.machine_detail", machine_id=m.id))

    return render_template("admin/machine_form.html", mode="new",
                           shops=list_shops(), form_data={})


@admin_bp.route("/machines/<int:machine_id>")
@login_required
def machine_detail(machine_id: int):
    _require(P.MACHINE_VIEW)
    m = machine_service.get_machine(machine_id)
    if not m or m.is_deleted:
        abort(404)
    return render_template("admin/machine_detail.html", machine=m)


@admin_bp.route("/machines/<int:machine_id>/edit", methods=["GET", "POST"])
@login_required
def machine_edit(machine_id: int):
    _require(P.MACHINE_EDIT)
    m = machine_service.get_machine(machine_id)
    if not m or m.is_deleted:
        abort(404)

    if request.method == "POST":
        try:
            machine_service.update_machine(
                m.id,
                name=ftext("name", max_len=255),
                model=ftext("model", max_len=128),
                unit=ftext("unit", max_len=64),
                description=ftext("description", max_len=2000),
                status=ftext("status", max_len=32) or None,
            )
        except ValueError as e:
            flash(str(e), "error")
            return render_template("admin/machine_form.html", mode="edit",
                                   shops=list_shops(), form_data=request.form,
                                   machine=m)

        audit_service.log("machine.update", entity_type="machine",
                          entity_id=m.id, shop_id=m.shop_id)
        flash("Machine အချက်အလက် ပြင်ပြီးပါပြီ။", "success")
        return redirect(url_for("admin.machine_detail", machine_id=m.id))

    return render_template("admin/machine_form.html", mode="edit",
                           shops=list_shops(), form_data={}, machine=m)


@admin_bp.route("/machines/<int:machine_id>/archive", methods=["POST"])
@login_required
def machine_archive(machine_id: int):
    _require(P.MACHINE_DELETE)
    m = machine_service.get_machine(machine_id)
    if not m or m.is_deleted:
        abort(404)
    try:
        machine_service.archive_machine(m.id)
        audit_service.log("machine.archive", entity_type="machine",
                          entity_id=m.id, shop_id=m.shop_id)
        flash(f"Machine '{m.name}' ကို Archive လုပ်ပြီးပါပြီ။", "info")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.machines_list"))


# ----------------------------------------------------------------
# Aliases
# ----------------------------------------------------------------
@admin_bp.route("/machines/<int:machine_id>/aliases/add", methods=["POST"])
@login_required
def machine_alias_add(machine_id: int):
    _require(P.MACHINE_EDIT)
    m = machine_service.get_machine(machine_id)
    if not m or m.is_deleted:
        abort(404)
    alias = ftext("alias", max_len=255)
    alias_type = ftext("alias_type", max_len=32) or "KEYWORD"
    try:
        machine_service.add_alias(m.id, alias, alias_type=alias_type)
        audit_service.log("machine.alias.add", entity_type="machine",
                          entity_id=m.id, shop_id=m.shop_id,
                          details={"alias": alias})
        flash(f"Alias '{alias}' ထည့်ပြီးပါပြီ။", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.machine_detail", machine_id=m.id))


@admin_bp.route("/machines/aliases/<int:alias_id>/remove", methods=["POST"])
@login_required
def machine_alias_remove(alias_id: int):
    _require(P.MACHINE_EDIT)
    a = db.session.get(MachineAlias, alias_id)
    if not a:
        abort(404)
    mid = a.machine_id
    try:
        machine_service.remove_alias(alias_id)
        audit_service.log("machine.alias.remove", entity_type="machine",
                          entity_id=mid, details={"alias_id": alias_id})
        flash("Alias ဖျက်ပြီးပါပြီ။", "info")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.machine_detail", machine_id=mid))


# ================================================================
# Machine Codes (Excel Import)
# ================================================================
from app.ingestion import machine_code_importer as mci
from app.models import MachineCode, MachineCodeSource
from app.services import file_service
from flask import current_app


@admin_bp.route("/machine-codes")
@login_required
def machine_codes_list():
    _require(P.MACHINE_CODE_VIEW)

    shop_code = request.args.get("shop", "").strip().upper() or None
    q = request.args.get("q", "").strip()

    shop = get_shop_by_code(shop_code) if shop_code else None

    query = MachineCode.query
    if shop:
        query = query.filter_by(shop_id=shop.id)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            db.or_(
                db.func.lower(MachineCode.code).like(like),
                db.func.lower(db.func.coalesce(MachineCode.machine_name, "")).like(like),
                db.func.lower(db.func.coalesce(MachineCode.model, "")).like(like),
                db.func.lower(db.func.coalesce(MachineCode.unit, "")).like(like),
            )
        )

    page = request.args.get("page", type=int, default=1)
    pagination = query.order_by(MachineCode.id.desc()).paginate(
        page=page, per_page=50, error_out=False
    )

    return render_template(
        "admin/machine_codes.html",
        pagination=pagination,
        shops=list_shops(),
        current_shop=shop_code or "",
        q=q,
    )


@admin_bp.route("/machine-codes/import", methods=["GET", "POST"])
@login_required
def machine_codes_import():
    _require(P.MACHINE_CODE_IMPORT)

    if request.method == "POST":
        shop_code = ftext("shop", max_len=16)
        shop = get_shop_by_code(shop_code)
        if not shop:
            flash("ဆိုင်ကုဒ် မှန်ကန်စွာ ရွေးပါ။", "error")
            return render_template("admin/machine_code_import.html",
                                   shops=list_shops(), mode="upload")

        f = request.files.get("file")
        if not f or not f.filename:
            flash("Excel ဖိုင် ရွေးပါ။", "error")
            return render_template("admin/machine_code_import.html",
                                   shops=list_shops(), mode="upload")

        try:
            meta = file_service.save_upload(f, category="excel")
        except ValueError as e:
            flash(str(e), "error")
            return render_template("admin/machine_code_import.html",
                                   shops=list_shops(), mode="upload")

        src = MachineCodeSource(
            shop_id=shop.id,
            original_filename=meta["original_filename"],
            stored_filename=meta["stored_filename"],
            file_path=meta["file_path"],
            file_hash=meta["file_hash"],
            uploaded_by_id=current_user.id,
            status="UPLOADED",
        )
        db.session.add(src)
        db.session.commit()

        audit_service.log("machine_code.upload", entity_type="machine_code_source",
                          entity_id=src.id, shop_id=shop.id,
                          details={"filename": src.original_filename})

        try:
            preview = mci.parse_excel_for_preview(
                meta["file_path"], shop=shop, source_id=src.id
            )
        except Exception as e:
            current_app.logger.exception("Excel parse failed: %s", e)
            src.status = "FAILED"
            src.notes = f"Parse error: {e}"
            db.session.commit()
            flash("Excel ဖတ်လို့ မရပါ။ Format ကို စစ်ပါ။", "error")
            return redirect(url_for("admin.machine_codes_import"))

        src.sheet_count = len(preview.sheets)
        src.row_count = preview.total_rows
        db.session.commit()

        return render_template(
            "admin/machine_code_import.html",
            shops=list_shops(), machines=_list_machines_for_teach(), mode="preview",
            preview=preview, source=src, shop=shop,
        )

    return render_template("admin/machine_code_import.html",
                           shops=list_shops(), mode="upload")


@admin_bp.route("/machine-codes/import/<int:source_id>/commit", methods=["POST"])
@login_required
def machine_codes_import_commit(source_id: int):
    _require(P.MACHINE_CODE_IMPORT)

    src = db.session.get(MachineCodeSource, source_id)
    if not src:
        abort(404)
    if src.status not in ("UPLOADED", "REVIEW_REQUIRED"):
        flash("ဒီ import ကို ပြီးသွားပါပြီ။", "warning")
        return redirect(url_for("admin.machine_codes_list"))

    shop = db.session.get(Shop, src.shop_id)
    if not shop:
        abort(404)

    try:
        preview = mci.parse_excel_for_preview(
            src.file_path, shop=shop, source_id=src.id
        )
        stats = mci.commit_import(src, preview.valid_rows)

        src.status = "REVIEW_REQUIRED"
        src.imported_count = stats["imported"]
        src.skipped_count = len(preview.invalid_rows) + len(preview.conflict_rows)
        src.duplicate_count = len(preview.duplicate_rows)
        src.conflict_count = len(preview.conflict_rows)
        db.session.commit()

        audit_service.log(
            "machine_code.import", entity_type="machine_code_source",
            entity_id=src.id, shop_id=shop.id,
            details=stats,
        )
        msg = (
            f"Import အောင်မြင်ပါပြီ — imported: {stats['imported']}, "
            f"failed: {stats.get('failed', 0)}, "
            f"skipped: {src.skipped_count}, duplicates: {src.duplicate_count}, "
            f"conflicts: {src.conflict_count}"
        )
        if stats.get("errors"):
            msg += " | errors: " + "; ".join(stats["errors"][:3])
        flash(msg, "success" if stats.get("failed", 0) == 0 else "warning")
    except Exception as e:
        current_app.logger.exception("Import commit failed: %s", e)
        db.session.rollback()
        src.status = "FAILED"
        src.notes = str(e)
        db.session.commit()
        flash("Import လုပ်ရာတွင် ပြဿနာ ရှိပါတယ်။", "error")

    return redirect(url_for("admin.machine_codes_list"))


@admin_bp.route("/machine-code-sources/<int:source_id>/delete", methods=["POST"])
@login_required
def machine_code_source_delete(source_id: int):
    """Delete source + file + codes + orphan machines."""
    _require(P.MACHINE_DELETE)
    import os
    from app.models import Machine

    src = db.session.get(MachineCodeSource, source_id)
    if not src:
        abort(404)

    shop_code = src.shop.code if src.shop else "—"
    filename = src.original_filename or "—"

    # 1. Delete file from disk
    if src.file_path:
        try:
            if os.path.isfile(src.file_path):
                os.remove(src.file_path)
        except Exception as e:
            flash(f"File delete warning: {e}", "warning")

    # 2. Get machine IDs referenced by this source
    machine_ids = db.session.query(MachineCode.machine_id).filter(
        MachineCode.source_id == source_id,
        MachineCode.machine_id.isnot(None),
    ).distinct().all()
    machine_ids = [m[0] for m in machine_ids]

    # 3. Delete codes from this source
    MachineCode.query.filter_by(source_id=source_id).delete()
    db.session.flush()

    # 4. Delete machines — ONLY if no other codes reference them
    deleted_machines = 0
    for mid in machine_ids:
        remaining = MachineCode.query.filter(
            MachineCode.machine_id == mid,
            MachineCode.is_deleted == False,  # noqa: E712
        ).count()
        if remaining == 0:
            m = db.session.get(Machine, mid)
            if m:
                db.session.delete(m)
                deleted_machines += 1

    # 5. Delete source
    db.session.delete(src)
    db.session.commit()

    audit_service.log(
        "machine_code_source.delete",
        entity_type="machine_code_source",
        entity_id=source_id,
        details={
            "shop": shop_code,
            "filename": filename,
            "machines_deleted": deleted_machines,
        },
    )

    flash(
        f"✓ Source '{filename}' ဖျက်ပြီ — Machines {deleted_machines} ပါ ဖျက်",
        "success",
    )
    return redirect(request.referrer or url_for("admin.machine_codes_list"))


@admin_bp.route("/machine-code-sources/<int:source_id>/approve", methods=["POST"])
@login_required
def machine_code_source_approve(source_id: int):
    _require(P.MACHINE_CODE_EDIT)

    src = db.session.get(MachineCodeSource, source_id)
    if not src:
        abort(404)

    n = mci.approve_source(src.id)
    src.status = "APPROVED"
    db.session.commit()

    audit_service.log("machine_code.approve", entity_type="machine_code_source",
                      entity_id=src.id, shop_id=src.shop_id,
                      details={"approved": n})
    flash(f"Machine Codes {n} ခု ကို Approve လုပ်ပြီးပါပြီ။", "success")
    return redirect(url_for("admin.machine_codes_list"))


# ================================================================
# Machine Code actions
# ================================================================
@admin_bp.route("/machine-codes/<int:code_id>/approve", methods=["POST"])
@login_required
def machine_code_approve(code_id: int):
    _require(P.MACHINE_CODE_EDIT)
    from app.services import machine_code_service as MCS
    ok = MCS.approve_code(code_id)
    if not ok:
        abort(404)
    audit_service.log("machine_code.approve_one", entity_type="machine_code",
                      entity_id=code_id)
    flash("Code ကို Approve လုပ်ပြီးပါပြီ။", "success")
    return redirect(request.referrer or url_for("admin.machine_codes_list"))


@admin_bp.route("/machine-codes/<int:code_id>/archive", methods=["POST"])
@login_required
def machine_code_archive(code_id: int):
    _require(P.MACHINE_CODE_EDIT)
    from app.services import machine_code_service as MCS
    ok = MCS.archive_code(code_id)
    if not ok:
        abort(404)
    audit_service.log("machine_code.archive_one", entity_type="machine_code",
                      entity_id=code_id)
    flash("Code ကို Archive လုပ်ပြီးပါပြီ။", "info")
    return redirect(request.referrer or url_for("admin.machine_codes_list"))


# ================================================================
# Knowledge + Quick Teach
# ================================================================
from app.services import knowledge_service as KS
from app.ingestion import quick_teach
from app.models import Knowledge, KnowledgeStatus


@admin_bp.route("/knowledge")
@login_required
def knowledge_list():
    _require(P.KNOWLEDGE_VIEW)

    shop_code = request.args.get("shop", "").strip().upper() or None
    status = request.args.get("status", "").strip().upper() or None
    q = request.args.get("q", "").strip()

    shop = get_shop_by_code(shop_code) if shop_code else None

    # ★ Default = global (all shops). If shop filter selected, narrow down.
    query = KS.list_knowledge(
        shop_id=shop.id if shop else None,
        status=status or None,
        q=q or None,
        global_shared=not bool(shop),   # if explicit shop chosen, filter; else global
    )
    page = request.args.get("page", type=int, default=1)
    pagination = query.paginate(page=page, per_page=30, error_out=False)

    return render_template(
        "admin/knowledge.html",
        pagination=pagination, shops=list_shops(),
        current_shop=shop_code or "", current_status=status or "", q=q,
    )


@admin_bp.route("/knowledge/<int:knowledge_id>")
@login_required
def knowledge_detail(knowledge_id: int):
    _require(P.KNOWLEDGE_VIEW)
    k = db.session.get(Knowledge, knowledge_id)
    if not k:
        abort(404)
    photos = KPS.list_photos(knowledge_id)
    return render_template("admin/knowledge_detail.html", knowledge=k, photos=photos)


@admin_bp.route("/knowledge/<int:knowledge_id>/edit", methods=["GET", "POST"])
@login_required
def knowledge_edit(knowledge_id: int):
    _require(P.KNOWLEDGE_CREATE)
    k = db.session.get(Knowledge, knowledge_id)
    if not k:
        flash("Knowledge မတွေ့ပါ။", "error")
        return redirect(url_for("admin.knowledge_list"))

    if request.method == "POST":
        mid_raw = (request.form.get("machine_id") or "").strip()
        machine_id = None
        if mid_raw:
            try:
                machine_id = int(mid_raw)
            except (ValueError, TypeError):
                machine_id = None

        try:
            KS.update_knowledge(
                knowledge_id,
                title=ftext("title", max_len=500),
                machine_id=machine_id,
                model=ftext("model", max_len=128) or None,
                unit=ftext("unit", max_len=64) or None,
                error_code=ftext("error_code", max_len=64) or None,
                category=ftext("category", max_len=64) or None,
                myanmar_content=ftext("myanmar_content", max_len=8000) or None,
                original_content=ftext("original_content", max_len=8000) or None,
                change_reason="admin_edit",
            )
            flash("✅ Knowledge ပြင်ပြီးပါပြီ။", "success")
            return redirect(url_for("admin.knowledge_detail", knowledge_id=knowledge_id))
        except ValueError as e:
            flash(str(e), "error")

    machines = _list_machines_for_teach(k.shop_id)
    return render_template(
        "admin/knowledge_edit.html",
        knowledge=k,
        error_codes=_list_error_codes_for_datalist(),
        machines=machines,
    )


@admin_bp.route("/knowledge/<int:knowledge_id>/approve", methods=["POST"])
@login_required
def knowledge_approve(knowledge_id: int):
    _require(P.KNOWLEDGE_APPROVE)
    try:
        KS.approve_knowledge(knowledge_id)
        audit_service.log("knowledge.approve", entity_type="knowledge",
                          entity_id=knowledge_id)
        flash("Knowledge ကို Approve လုပ်ပြီးပါပြီ။", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.knowledge_detail", knowledge_id=knowledge_id))


@admin_bp.route("/knowledge/<int:knowledge_id>/archive", methods=["POST"])
@login_required
def knowledge_archive(knowledge_id: int):
    _require(P.KNOWLEDGE_DELETE)
    try:
        KS.archive_knowledge(knowledge_id)
        audit_service.log("knowledge.archive", entity_type="knowledge",
                          entity_id=knowledge_id)
        flash("Knowledge ကို Archive လုပ်ပြီးပါပြီ။", "info")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.knowledge_list"))


# ----------------------------------------------------------------
# Quick Teach
# ----------------------------------------------------------------

def _list_machines_for_teach(shop_id=None):
    """List machines for quick teach dropdown (filter by shop)."""
    try:
        from app.services import machine_service as MS
        return MS.list_machines(shop_id=shop_id, only_active=True)
    except Exception:
        return []




def _list_error_codes_for_datalist(limit: int = 200):
    """Get distinct error codes from Knowledge + ErrorKnowledge — for datalist."""
    codes = set()
    try:
        from app.models import Knowledge, ErrorKnowledge
        # Knowledge
        for (c,) in (Knowledge.query
                     .filter(Knowledge.error_code.isnot(None),
                             Knowledge.error_code != "")
                     .with_entities(Knowledge.error_code)
                     .distinct().limit(limit).all()):
            if c and c.strip():
                codes.add(c.strip())
        # ErrorKnowledge
        for (c,) in (ErrorKnowledge.query
                     .filter(ErrorKnowledge.error_code.isnot(None),
                             ErrorKnowledge.error_code != "")
                     .with_entities(ErrorKnowledge.error_code)
                     .distinct().limit(limit).all()):
            if c and c.strip():
                codes.add(c.strip())
    except Exception as e:
        from flask import current_app
        try:
            current_app.logger.warning("error codes list failed: %s", e)
        except Exception:
            pass
    return sorted(codes)
@admin_bp.route("/teach/quick", methods=["GET", "POST"])
@login_required
def teach_quick():
    _require(P.KNOWLEDGE_CREATE)

    if request.method == "POST":
        shop_code = ftext("shop", max_len=16)
        shop = get_shop_by_code(shop_code)
        if not shop:
            flash("ဆိုင်ကုဒ် မှန်ကန်စွာ ရွေးပါ။", "error")
            return render_template("admin/quick_teach.html",
                                   shops=list_shops(), error_codes=_list_error_codes_for_datalist(), machines=_list_machines_for_teach(), mode="input",
                                   text=request.form.get("text", ""))

        raw_text = (request.form.get("text") or "").strip()
        if not raw_text:
            flash("စာသား ထည့်ပါ။", "error")
            return render_template("admin/quick_teach.html",
                                   shops=list_shops(), error_codes=_list_error_codes_for_datalist(), machines=_list_machines_for_teach(), mode="input",
                                   text=raw_text)

        machine_hint = ftext("machine_hint", max_len=255) or None

        # AI-powered (falls back to rules automatically)
        from app.ai import service as AI_SVC
        outcome = AI_SVC.quick_teach_extract(raw_text, machine_hint=machine_hint)
        fields = outcome.fields or {}

        return render_template(
            "admin/quick_teach.html",
            shops=list_shops(), error_codes=_list_error_codes_for_datalist(), machines=_list_machines_for_teach(shop.id if shop else None), mode="preview",
            text=raw_text, shop=shop, fields=fields,
            source=outcome.source,
            machine_hint=machine_hint or "",
        )

    return render_template("admin/quick_teach.html",
                           shops=list_shops(), error_codes=_list_error_codes_for_datalist(), machines=_list_machines_for_teach(), mode="input", text="")


@admin_bp.route("/teach/quick/save", methods=["POST"])
@login_required
def teach_quick_save():
    _require(P.KNOWLEDGE_CREATE)

    shop_code = ftext("shop", max_len=16)
    shop = get_shop_by_code(shop_code)
    if not shop:
        flash("ဆိုင်ကုဒ် မမှန်ကန်ပါ။", "error")
        return redirect(url_for("admin.teach_quick"))

    title = ftext("title", max_len=500)

    # ★ Machine — hybrid (dropdown + new text + auto-create)
    machine_obj = None
    mid_raw = request.form.get("machine_id") or ""
    mname_new = ftext("machine_name_new", max_len=255) or ftext("machine_name", max_len=255)

    if mid_raw.strip():
        # Dropdown ရွေး
        try:
            from app.models import Machine
            machine_obj = db.session.get(Machine, int(mid_raw))
        except (ValueError, TypeError):
            machine_obj = None

    # ★ Text input — machine အသစ် (dropdown မှာ မရှိရင်)
    if not machine_obj and mname_new:
        from app.models import Machine
        machine_obj = Machine.query.filter_by(
            name=mname_new, shop_id=shop.id, is_deleted=False
        ).first()
        if not machine_obj:
            # Auto create — machines table
            machine_obj = Machine(
                shop_id=shop.id,
                name=mname_new,
                status="ACTIVE",
            )
            db.session.add(machine_obj)
            db.session.flush()

    if machine_obj:
        m = machine_obj.name
    else:
        m = "Knowledge"

    u = ftext("unit", max_len=64)
    ec = ftext("error_code", max_len=64)

    if not title:
        title = m + (f" {u}" if u else "") + (f" Error {ec}" if ec else "")

    try:
        k = KS.create_knowledge(
            shop_id=shop.id,
            title=title,
            category="quick_teach",
            machine_id=machine_obj.id if machine_obj else None,
            model=ftext("model", max_len=128) or None,
            unit=u or None,
            error_code=ec or None,
            myanmar_content=(
                (ftext("problem", max_len=2000) or "") + "\n\n"
                + (ftext("finding", max_len=2000) or "") + "\n\n"
                + (ftext("action_taken", max_len=2000) or "") + "\n\n"
                + (ftext("result", max_len=2000) or "")
            ).strip(),
            original_content=ftext("original_text", max_len=8000) or None,
            original_language="my",
            confidence=float(ftext("confidence", max_len=8) or "0.7"),
            source_type="quick_teach",
            status=KnowledgeStatus.PENDING,
        )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("admin.teach_quick"))

    # ★ Upload photos if provided
    photos = request.files.getlist("photos")
    saved_photos = 0
    if photos:
        # Filter empty
        photos = [f for f in photos if f and f.filename]
        if photos:
            saved_photos, errs = KPS.add_photos_batch(
                knowledge_id=k.id,
                files=photos,
            )
            for e in (errs or [])[:3]:
                flash(f"⚠️ Photo skip: {e}", "warning")

    audit_service.log("knowledge.quick_teach", entity_type="knowledge",
                      entity_id=k.id, shop_id=shop.id,
                      details={"title": k.title, "photos": saved_photos})

    msg = "Knowledge ကို PENDING အဖြစ် သိမ်းပြီးပါပြီ။"
    if saved_photos:
        msg += f" · 📷 Photos {saved_photos} ပုံ ပါ သိမ်းပြီး။"
    flash(msg + " Approve လုပ်ရန် လိုအပ်ပါတယ်။", "success")
    return redirect(url_for("admin.knowledge_detail", knowledge_id=k.id))


@admin_bp.route("/knowledge/conflicts")
@login_required
def knowledge_conflicts():
    _require(P.KNOWLEDGE_VIEW)
    conflicts = KS.list_open_conflicts()
    return render_template("admin/knowledge_conflicts.html", conflicts=conflicts)


@admin_bp.route("/knowledge/conflicts/<int:conflict_id>/resolve", methods=["POST"])
@login_required
def knowledge_conflict_resolve(conflict_id: int):
    _require(P.KNOWLEDGE_APPROVE)
    note = ftext("note", max_len=2000)
    try:
        KS.resolve_conflict(conflict_id, note=note)
        audit_service.log("knowledge.conflict.resolve",
                          entity_type="knowledge_conflict",
                          entity_id=conflict_id)
        flash("Conflict ကို Resolved အဖြစ် သတ်မှတ်ပြီးပါပြီ။", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.knowledge_conflicts"))


# ================================================================
# Re-added: Unified Search + Image Ingestion
# (Lost during PART 17 teach_quick replacement — restored here)
# ================================================================
from app.search import unified_search as US
from app.ingestion import image_ingestor as II


@admin_bp.route("/search")
@login_required
def search_page():
    _require(P.DASHBOARD_VIEW)

    q = (request.args.get("q") or "").strip()
    shop_code = (request.args.get("shop") or "").strip().upper() or None
    only_approved = request.args.get("approved", "1") == "1"

    shop = get_shop_by_code(shop_code) if shop_code else None

    result = None
    if q:
        result = US.search(
            query=q,
            shop_id=shop.id if shop else None,
            shop_code=shop.code if shop else None,
            only_approved=only_approved,
        )

    return render_template(
        "admin/search.html",
        q=q, result=result, shops=list_shops(),
        current_shop=shop_code or "",
        only_approved=only_approved,
    )


@admin_bp.route("/images/ingest", methods=["GET", "POST"])
@login_required
def image_ingest():
    _require(P.KNOWLEDGE_CREATE)

    if request.method == "POST":
        shop_code = ftext("shop", max_len=16)
        shop = get_shop_by_code(shop_code)
        if not shop:
            flash("ဆိုင်ကုဒ် မှန်ကန်စွာ ရွေးပါ။", "error")
            return render_template("admin/image_ingest.html",
                                   shops=list_shops(), mode="input")

        f = request.files.get("file")
        if not f or not f.filename:
            flash("ပုံဖိုင် ရွေးပါ။", "error")
            return render_template("admin/image_ingest.html",
                                   shops=list_shops(), mode="input")

        try:
            meta = FS2.save_upload(f, category="image")
        except ValueError as e:
            flash(str(e), "error")
            return render_template("admin/image_ingest.html",
                                   shops=list_shops(), mode="input")

        caption = ftext("caption", max_len=500)
        description = ftext("description", max_len=2000)

        try:
            doc = II.ingest_image(
                meta["file_path"], meta["original_filename"],
                admin_caption=caption, admin_description=description,
            )
        except Exception as e:
            current_app.logger.exception("Image ingestion failed: %s", e)
            flash("ပုံ ဖတ်လို့ မရပါ။", "error")
            return redirect(url_for("admin.image_ingest"))

        try:
            MS.save_media(
                uploaded_file=f, shop_id=shop.id, category="image",
                caption=caption, description=description,
            )
        except Exception:
            pass

        return render_template(
            "admin/image_ingest.html",
            shops=list_shops(), mode="preview",
            shop=shop, doc=doc,
        )

    return render_template("admin/image_ingest.html",
                           shops=list_shops(), mode="input")


@admin_bp.route("/images/ingest/save", methods=["POST"])
@login_required
def image_ingest_save():
    _require(P.KNOWLEDGE_CREATE)

    shop = get_shop_by_code(ftext("shop", max_len=16))
    if not shop:
        flash("ဆိုင်ကုဒ် မမှန်ကန်ပါ။", "error")
        return redirect(url_for("admin.image_ingest"))

    title = ftext("title", max_len=500) or "Image knowledge"
    content = ftext("content", max_len=8000)
    machine_name = ftext("machine_name", max_len=255) or None
    unit = ftext("unit", max_len=64) or None
    error_code = ftext("error_code", max_len=64) or None
    source_file = ftext("source_file", max_len=512) or None

    if not content:
        flash("Content ဗလာ ဖြစ်နေတယ်။", "error")
        return redirect(url_for("admin.image_ingest"))

    try:
        k = KS.create_knowledge(
            shop_id=shop.id,
            title=title,
            category="image",
            model=None,
            unit=unit,
            error_code=error_code,
            myanmar_content=content,
            original_content=content,
            original_language="my",
            confidence=0.6,
            source_type="image",
            source_file=source_file,
            status=KnowledgeStatus.PENDING,
        )
        audit_service.log("knowledge.image_ingest", entity_type="knowledge",
                          entity_id=k.id, shop_id=shop.id,
                          details={"file": source_file})
        flash("Image knowledge ကို PENDING အဖြစ် သိမ်းပြီးပါပြီ။", "success")
    except ValueError as e:
        flash(str(e), "error")

    return redirect(url_for("admin.knowledge_list", status="PENDING"))


# ================================================================
# Re-added: Document Ingest (PDF/DOCX/Excel/TXT)
# (Lost during PART 17 teach_quick replacement — restored)
# ================================================================
from app.ingestion import document_ingestor as DI


@admin_bp.route("/ingest", methods=["GET", "POST"])
@login_required
def ingest_document_page():
    _require(P.KNOWLEDGE_CREATE)

    if request.method == "POST":
        shop_code = ftext("shop", max_len=16)
        shop = get_shop_by_code(shop_code)
        if not shop:
            flash("ဆိုင်ကုဒ် မှန်ကန်စွာ ရွေးပါ။", "error")
            return render_template("admin/ingest.html",
                                   shops=list_shops(), mode="input")

        f = request.files.get("file")
        if not f or not f.filename:
            flash("ဖိုင် ရွေးပါ။", "error")
            return render_template("admin/ingest.html",
                                   shops=list_shops(), mode="input")

        try:
            meta = FS2.save_upload(f)
        except ValueError as e:
            flash(str(e), "error")
            return render_template("admin/ingest.html",
                                   shops=list_shops(), mode="input")

        try:
            doc = DI.ingest_document(meta["file_path"], meta["original_filename"])
        except Exception as e:
            current_app.logger.exception("Ingestion failed: %s", e)
            flash("ဖိုင် ဖတ်လို့ မရပါ။ Format ကို စစ်ပါ။", "error")
            return redirect(url_for("admin.ingest_document_page"))

        # Admin machine hint overrides auto-detected values if provided
        admin_hint = ftext("machine_hint", max_len=255)
        if admin_hint:
            for c in doc.candidates:
                c.machine_name = admin_hint
                c.machine_hint = admin_hint

        return render_template(
            "admin/ingest.html",
            shops=list_shops(), mode="preview",
            shop=shop, doc=doc,
        )

    return render_template("admin/ingest.html",
                           shops=list_shops(), mode="input")


@admin_bp.route("/ingest/save", methods=["POST"])
@login_required
def ingest_document_save():
    _require(P.KNOWLEDGE_CREATE)

    shop = get_shop_by_code(ftext("shop", max_len=16))
    if not shop:
        flash("ဆိုင်ကုဒ် မမှန်ကန်ပါ။", "error")
        return redirect(url_for("admin.ingest_document_page"))

    selected = request.form.getlist("selected")
    if not selected:
        flash("ဘယ် candidate တွေကို သိမ်းမလဲ ရွေးပါ။", "error")
        return redirect(url_for("admin.ingest_document_page"))

    source_file = ftext("source_file", max_len=512)
    saved = 0

    for idx_s in selected:
        try:
            i = int(idx_s)
        except ValueError:
            continue

        title = ftext(f"cand_{i}_title", max_len=500) or "Untitled"
        content = ftext(f"cand_{i}_content", max_len=8000)
        machine_name = ftext(f"cand_{i}_machine", max_len=255) or None
        model = ftext(f"cand_{i}_model", max_len=128) or None
        unit = ftext(f"cand_{i}_unit", max_len=64) or None
        error_code = ftext(f"cand_{i}_error_code", max_len=64) or None
        source_type = ftext(f"cand_{i}_source_type", max_len=32) or None
        source_page = ftext(f"cand_{i}_source_page", max_len=32) or None
        source_sheet = ftext(f"cand_{i}_source_sheet", max_len=128) or None
        source_row_s = ftext(f"cand_{i}_source_row", max_len=16)
        try:
            source_row = int(source_row_s) if source_row_s else None
        except ValueError:
            source_row = None

        if not content:
            continue

        # ★ If error_code present → save as ErrorKnowledge
        if error_code:
            try:
                ek = ES.create_error_knowledge(
                    shop_id=shop.id,
                    error_code=error_code,
                    error_name=title[:500],
                    machine_name=machine_name,
                    model=model,
                    unit=unit,
                    symptoms=None,
                    cause=None,
                    check_steps=None,
                    solution=content,
                    notes=None,
                    status="PENDING",
                )
                ek.source_type = source_type or "ingest"
                ek.source_file = source_file or None
                saved += 1
            except ValueError as e:
                current_app.logger.warning("Skipped err candidate %s: %s", i, e)
        else:
            # General Knowledge
            try:
                KS.create_knowledge(
                    shop_id=shop.id,
                    title=title,
                    category="ingested",
                    model=model,
                    unit=unit,
                    error_code=error_code,
                    myanmar_content=content,
                    original_content=content,
                    original_language="my",
                    confidence=0.7,
                    source_type=source_type or "ingest",
                    source_file=source_file or None,
                    source_page=source_page,
                    source_sheet=source_sheet,
                    source_row=source_row,
                    status=KnowledgeStatus.PENDING,
                )
                saved += 1
            except ValueError as e:
                current_app.logger.warning("Skipped candidate %s: %s", i, e)

    db.session.commit()
    audit_service.log("knowledge.ingest", entity_type="knowledge_bulk",
                      shop_id=shop.id,
                      details={"saved": saved, "source": source_file})
    flash(f"{saved} items PENDING အဖြစ် သိမ်းပြီးပါပြီ။", "success")
    return redirect(url_for("admin.knowledge_list", status="PENDING"))


@admin_bp.route("/errors")
@login_required
def errors_list():
    _require(P.ERROR_VIEW)
    shop_code = request.args.get("shop", "").strip().upper() or None
    status = request.args.get("status", "").strip().upper() or None
    q = request.args.get("q", "").strip()

    shop = get_shop_by_code(shop_code) if shop_code else None

    # ★ Default = global (all shops). If shop filter selected, narrow down.
    from app.services import error_service as _ES
    query = _ES.list_error_knowledge(
        shop_id=shop.id if shop else None,
        status=status or None,
        q=q or None,
        global_shared=not bool(shop),   # if explicit shop chosen, filter; else global
    )
    page = request.args.get("page", type=int, default=1)
    pagination = query.paginate(page=page, per_page=30, error_out=False)

    return render_template(
        "admin/errors.html",
        pagination=pagination, shops=list_shops(),
        current_shop=shop_code or "", current_status=status or "", q=q,
    )


@admin_bp.route("/errors/new", methods=["GET", "POST"])
@login_required
def error_new():
    _require(P.ERROR_CREATE)

    if request.method == "POST":
        shop = get_shop_by_code(ftext("shop", max_len=16))
        if not shop:
            flash("ဆိုင်ကုဒ် မှန်ကန်စွာ ရွေးပါ။", "error")
            return render_template("admin/error_form.html", shops=list_shops(),
                                   mode="new", form_data=request.form)

        try:
            ek = ES.create_error_knowledge(
                shop_id=shop.id,
                error_code=ftext("error_code", max_len=64) or None,
                error_name=ftext("error_name", max_len=512) or None,
                machine_name=ftext("machine_name", max_len=255) or None,
                model=ftext("model", max_len=128) or None,
                unit=ftext("unit", max_len=64) or None,
                symptoms=ftext("symptoms", max_len=4000) or None,
                cause=ftext("cause", max_len=4000) or None,
                check_steps=ftext("check_steps", max_len=4000) or None,
                solution=ftext("solution", max_len=4000) or None,
                notes=ftext("notes", max_len=2000) or None,
                status="PENDING",
            )
        except ValueError as e:
            flash(str(e), "error")
            return render_template("admin/error_form.html", shops=list_shops(),
                                   mode="new", form_data=request.form)

        audit_service.log("error_knowledge.create", entity_type="error_knowledge",
                          entity_id=ek.id, shop_id=shop.id)
        flash("Error Knowledge ကို PENDING အဖြစ် သိမ်းပြီးပါပြီ။", "success")
        return redirect(url_for("admin.errors_list"))

    return render_template("admin/error_form.html", shops=list_shops(),
                           mode="new", form_data={})


@admin_bp.route("/errors/<int:error_id>/edit", methods=["GET", "POST"])
@login_required
def error_edit(error_id: int):
    _require(P.ERROR_EDIT)
    ek = db.session.get(ErrorKnowledge, error_id)
    if not ek:
        abort(404)

    if request.method == "POST":
        try:
            ES.update_error_knowledge(
                ek.id,
                error_code=ftext("error_code", max_len=64),
                error_name=ftext("error_name", max_len=512),
                machine_name=ftext("machine_name", max_len=255),
                model=ftext("model", max_len=128),
                unit=ftext("unit", max_len=64),
                symptoms=ftext("symptoms", max_len=4000),
                cause=ftext("cause", max_len=4000),
                check_steps=ftext("check_steps", max_len=4000),
                solution=ftext("solution", max_len=4000),
                notes=ftext("notes", max_len=2000),
            )
            audit_service.log("error_knowledge.update", entity_type="error_knowledge",
                              entity_id=ek.id, shop_id=ek.shop_id)
            flash("Error Knowledge ပြင်ပြီးပါပြီ။", "success")
            return redirect(url_for("admin.errors_list"))
        except ValueError as e:
            flash(str(e), "error")

    return render_template("admin/error_form.html", shops=list_shops(),
                           mode="edit", form_data={}, error=ek)


@admin_bp.route("/errors/<int:error_id>/approve", methods=["POST"])
@login_required
def error_approve(error_id: int):
    _require(P.ERROR_APPROVE)
    try:
        ES.approve_error_knowledge(error_id)
        audit_service.log("error_knowledge.approve", entity_type="error_knowledge",
                          entity_id=error_id)
        flash("Error Knowledge ကို Approve လုပ်ပြီးပါပြီ။", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.errors_list"))


# ----------------------------------------------------------------
# Error Cases
# ----------------------------------------------------------------


@admin_bp.route("/errors/bulk-approve", methods=["POST"])
@login_required
def errors_bulk_approve():
    """Bulk approve selected error knowledge rows."""
    _require(P.ERROR_APPROVE)

    ids = request.form.getlist("selected")
    if not ids:
        flash("Approve လုပ်ဖို့ row တွေ ရွေးပါ။", "error")
        return redirect(request.referrer or url_for("admin.errors_list"))

    from app.models.base import utcnow
    count = 0
    for sid in ids:
        try:
            eid = int(sid)
        except ValueError:
            continue
        ek = db.session.get(ErrorKnowledge, eid)
        if not ek or ek.status not in ("DRAFT", "PENDING"):
            continue
        ek.status = "APPROVED"
        ek.approved_by_id = current_user.id
        ek.approved_at = utcnow()
        count += 1

    db.session.commit()
    audit_service.log("error_knowledge.bulk_approve",
                      entity_type="error_knowledge_bulk",
                      details={"count": count})
    flash(f"{count} Error Knowledge ကို Approve လုပ်ပြီးပါပြီ။", "success")
    return redirect(request.referrer or url_for("admin.errors_list"))




@admin_bp.route("/errors/<int:error_id>/delete", methods=["GET", "POST"])
@login_required
def error_delete(error_id: int):
    _require(P.ERROR_APPROVE)
    ok = ES.delete_error_knowledge(error_id)
    if ok:
        audit_service.log("error_knowledge.delete",
                          entity_type="error_knowledge", entity_id=error_id)
        flash("✅ ဖျက်ပြီးပါပြီ။", "success")
    else:
        flash("❌ မတွေ့ပါ။", "error")
    return redirect(request.referrer or url_for("admin.errors_list"))


@admin_bp.route("/errors/bulk-delete", methods=["POST"])
@login_required
def errors_bulk_delete():
    _require(P.ERROR_APPROVE)
    ids_raw = request.form.getlist("selected")
    if not ids_raw:
        flash("ဖျက်ဖို့ row တွေ ရွေးပါ။", "error")
        return redirect(request.referrer or url_for("admin.errors_list"))

    ids = []
    for sid in ids_raw:
        try:
            ids.append(int(sid))
        except (ValueError, TypeError):
            continue

    count = ES.bulk_delete_error_knowledge(ids)
    audit_service.log("error_knowledge.bulk_delete",
                      entity_type="error_knowledge_bulk",
                      details={"count": count, "ids": ids[:20]})
    flash(f"✅ {count} ခု ဖျက်ပြီးပါပြီ။", "success")
    return redirect(url_for("admin.errors_list"))


@admin_bp.route("/error-cases")
@login_required
def error_cases_list():
    _require(P.ERROR_VIEW)
    shop_code = request.args.get("shop", "").strip().upper() or None
    status = request.args.get("status", "").strip().upper() or None
    code = request.args.get("code", "").strip() or None

    shop = get_shop_by_code(shop_code) if shop_code else None

    from app.services import error_service as _ES
    query = _ES.list_error_cases(
        shop_id=shop.id if shop else None,
        status=status or None,
        error_code=code or None,
        global_shared=not bool(shop),
    )
    page = request.args.get("page", type=int, default=1)
    pagination = query.paginate(page=page, per_page=30, error_out=False)

    return render_template(
        "admin/error_cases.html",
        pagination=pagination, shops=list_shops(),
        current_shop=shop_code or "", current_status=status or "", code=code or "",
    )


@admin_bp.route("/error-cases/new", methods=["GET", "POST"])
@login_required
def error_case_new():
    _require(P.ERROR_CREATE)

    if request.method == "POST":
        shop = get_shop_by_code(ftext("shop", max_len=16))
        if not shop:
            flash("ဆိုင်ကုဒ် မှန်ကန်စွာ ရွေးပါ။", "error")
            return render_template("admin/error_case_form.html",
                                   shops=list_shops(), mode="new", form_data=request.form)

        # ★ Save uploaded photos (up to 10)
        photo_paths = []
        files = request.files.getlist("photos")
        for _f in files:
            if _f and _f.filename:
                import os, uuid
                from app.config import UPLOAD_ROOT
                ext = os.path.splitext(_f.filename)[1].lower()
                if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"):
                    _d = UPLOAD_ROOT / "photos"
                    _d.mkdir(parents=True, exist_ok=True)
                    _fname = f"errcase_{uuid.uuid4().hex[:12]}{ext}"
                    _f.save(str(_d / _fname))
                    photo_paths.append(f"photos/{_fname}")
                    if len(photo_paths) >= 10:
                        break

        try:
            ec = ES.create_error_case(
                shop_id=shop.id,
                error_code=ftext("error_code", max_len=64) or None,
                machine_name=ftext("machine_name", max_len=255) or None,
                model=ftext("model", max_len=128) or None,
                unit=ftext("unit", max_len=64) or None,
                problem=ftext("problem", max_len=4000) or None,
                finding=ftext("finding", max_len=4000) or None,
                action_taken=ftext("action_taken", max_len=4000) or None,
                result=ftext("result", max_len=4000) or None,
                myanmar_content=ftext("myanmar_content", max_len=8000) or None,
                photo_paths=photo_paths,
                status="PENDING",
            )
        except ValueError as e:
            flash(str(e), "error")
            return render_template("admin/error_case_form.html",
                                   shops=list_shops(), mode="new", form_data=request.form)

        audit_service.log("error_case.create", entity_type="error_case",
                          entity_id=ec.id, shop_id=shop.id)
        flash("Error Case ကို PENDING အဖြစ် သိမ်းပြီးပါပြီ။", "success")
        return redirect(url_for("admin.error_cases_list"))

    return render_template("admin/error_case_form.html",
                           shops=list_shops(), mode="new", form_data={})


@admin_bp.route("/error-cases/<int:case_id>/photo")
@login_required
def error_case_photo(case_id: int):
    """Serve error case photo."""
    from flask import send_from_directory, abort
    from app.config import UPLOAD_ROOT
    ec = ErrorCase.query.get_or_404(case_id)
    if not ec.photo_path:
        abort(404)
    return send_from_directory(str(UPLOAD_ROOT), ec.photo_path)


@admin_bp.route("/error-cases/<int:case_id>/approve", methods=["POST"])
@login_required
def error_case_approve(case_id: int):
    _require(P.ERROR_APPROVE)
    try:
        ES.approve_error_case(case_id)
        audit_service.log("error_case.approve", entity_type="error_case",
                          entity_id=case_id)
        flash("Error Case ကို Approve လုပ်ပြီးပါပြီ။", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.error_cases_list"))


# ================================================================
# Re-added: Files & Photos + AI Test Center
# (Lost during PART 17 teach_quick replacement — restored)
# ================================================================
from app.services import telegram_notify_service as TN
from app.services import media_service as MS
from app.models import MediaCategory, MediaFile
from app.ai import service as AI_SVC
from app.ai import rag as AI_RAG


@admin_bp.route("/files")
@login_required
def files_list():
    _require(P.FILE_VIEW)

    shop_code = request.args.get("shop", "").strip().upper() or None
    category = request.args.get("category", "").strip().lower() or None
    q = request.args.get("q", "").strip()

    shop = get_shop_by_code(shop_code) if shop_code else None

    files = MS.list_media(
        shop_id=shop.id if shop else None,
        category=category or None,
        q=q or None,
    )

    return render_template(
        "admin/files.html",
        files=files, shops=list_shops(),
        current_shop=shop_code or "",
        current_category=category or "", q=q,
        categories=[MediaCategory.IMAGE, MediaCategory.PDF, MediaCategory.EXCEL,
                    MediaCategory.WORD, MediaCategory.DOCUMENT, MediaCategory.OTHER],
    )


@admin_bp.route("/files/upload", methods=["POST"])
@login_required
def files_upload():
    _require(P.FILE_UPLOAD)

    shop_code = ftext("shop", max_len=16)
    shop = get_shop_by_code(shop_code) if shop_code else None

    f = request.files.get("file")
    if not f or not f.filename:
        flash("ဖိုင် ရွေးပါ။", "error")
        return redirect(url_for("admin.files_list"))

    try:
        mf = MS.save_media(
            uploaded_file=f,
            shop_id=shop.id if shop else None,
            category=ftext("category", max_len=32) or None,
            caption=ftext("caption", max_len=500) or None,
            description=ftext("description", max_len=2000) or None,
        )
        flash(f"ဖိုင် '{mf.original_filename}' upload လုပ်ပြီးပါပြီ။", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.files_list"))


@admin_bp.route("/files/<int:media_id>")
@login_required
def file_detail(media_id: int):
    _require(P.FILE_VIEW)
    mf = MS.get_media(media_id)
    if not mf or mf.is_deleted:
        abort(404)
    return render_template("admin/file_detail.html", media=mf)


@admin_bp.route("/files/<int:media_id>/download")
@login_required
def file_download(media_id: int):
    _require(P.FILE_VIEW)
    resp = MS.send_media_file(media_id)
    if resp is None:
        abort(404)
    return resp


@admin_bp.route("/files/<int:media_id>/delete", methods=["POST"])
@login_required
def file_delete(media_id: int):
    _require(P.FILE_DELETE)
    mf = MS.get_media(media_id)
    if not mf or mf.is_deleted:
        abort(404)
    MS.delete_media(media_id)
    flash("ဖိုင် ဖျက်ပြီးပါပြီ။", "info")
    return redirect(url_for("admin.files_list"))


# ----------------------------------------------------------------
# AI Test Center
# ----------------------------------------------------------------
@admin_bp.route("/ai/test", methods=["GET", "POST"])
@login_required
def ai_test():
    _require(P.DASHBOARD_VIEW)

    question = ""
    shop_code = ""
    shop = None
    result = None
    search = None
    ai_status = AI_SVC.status()

    if request.method == "POST":
        question = ftext("question", max_len=2000)
        shop_code = ftext("shop", max_len=16)
        shop = get_shop_by_code(shop_code) if shop_code else None

        if question:
            search = US.search(
                query=question,
                shop_id=shop.id if shop else None,
                shop_code=shop.code if shop else None,
                only_approved=False,
            )
            result = AI_RAG.answer_question(
                user_question=question,
                shop_code=shop.code if shop else None,
                shop_id=shop.id if shop else None,
                only_approved=True,
            )

    return render_template(
        "admin/ai_test.html",
        question=question,
        shop_code=shop_code,
        shops=list_shops(),
        result=result,
        search=search,
        ai_status=ai_status,
    )


# ================================================================
# Tasks
# ================================================================
from datetime import date as _date
from app.services import task_service as TS
from app.services import task_nl_parser as TNP
from app.models import Task, TaskHistory


def _parse_date(s: str | None):
    if not s:
        return None
    try:
        y, m, d = s.split("-")
        return _date(int(y), int(m), int(d))
    except Exception:
        return None


@admin_bp.route("/tasks")
@login_required
def tasks_list():
    _require(P.TASK_VIEW)

    tab = (request.args.get("tab") or "today").strip().lower()
    shop_code = request.args.get("shop", "").strip().upper() or None
    shop = get_shop_by_code(shop_code) if shop_code else None
    shop_id = shop.id if shop else None

    today = TS.local_today()
    tasks: list = []

    if tab == "today":
        tasks = TS.tasks_for_date(on=today, shop_id=shop_id)
    elif tab == "upcoming":
        tasks = [t for _, t in TS.upcoming_tasks(days=14, shop_id=shop_id)]
    elif tab == "overdue":
        tasks = TS.overdue_tasks(shop_id=shop_id)
    elif tab == "completed":
        q = Task.query.filter(
            Task.is_deleted.is_(False), Task.status == "COMPLETED"
        )
        if shop_id:
            q = q.filter(Task.shop_id == shop_id)
        tasks = q.order_by(Task.id.desc()).limit(200).all()
    else:  # all
        q = Task.query.filter(Task.is_deleted.is_(False))
        if shop_id:
            q = q.filter(Task.shop_id == shop_id)
        tasks = q.order_by(Task.id.desc()).limit(300).all()

    return render_template(
        "admin/tasks.html",
        tab=tab, tasks=tasks, shops=list_shops(),
        current_shop=shop_code or "",
        today=today,
    )


@admin_bp.route("/tasks/new", methods=["GET", "POST"])
@login_required
def task_new():
    _require(P.TASK_CREATE)

    parsed = None
    if request.method == "POST":
        shop = get_shop_by_code(ftext("shop", max_len=16))
        if not shop:
            flash("ဆိုင်ကုဒ် မှန်ကန်စွာ ရွေးပါ။", "error")
            return render_template("admin/task_form.html",
                                   shops=list_shops(), mode="input")

        raw_text = ftext("raw_text", max_len=2000)
        if raw_text:
            parsed = TNP.parse(raw_text)
            return render_template(
                "admin/task_form.html",
                shops=list_shops(), mode="preview",
                shop=shop, parsed=parsed, raw_text=raw_text,
            )

        # Direct save path
        try:
            t = TS.create_task(
                shop_id=shop.id,
                title=ftext("title", max_len=500),
                description=ftext("description", max_len=2000) or None,
                frequency=ftext("frequency", max_len=16) or "DAILY",
                weekday=fint("weekday", None),
                day_of_month=fint("day_of_month", None),
                month=fint("month", None),
                specific_date=_parse_date(ftext("specific_date", max_len=16) or None),
                task_time=ftext("task_time", max_len=8) or None,
                priority=ftext("priority", max_len=16) or "NORMAL",
            )
            audit_service.log("task.create", entity_type="task",
                              entity_id=t.id, shop_id=shop.id)
            flash("Task ကို ဖန်တီးပြီးပါပြီ။", "success")
            return redirect(url_for("admin.tasks_list"))
        except ValueError as e:
            flash(str(e), "error")
            return render_template("admin/task_form.html",
                                   shops=list_shops(), mode="input")

    return render_template("admin/task_form.html",
                           shops=list_shops(), mode="input")


@admin_bp.route("/tasks/new/save", methods=["POST"])
@login_required
def task_new_save():
    _require(P.TASK_CREATE)

    shop = get_shop_by_code(ftext("shop", max_len=16))
    if not shop:
        flash("ဆိုင်ကုဒ် မမှန်ကန်ပါ။", "error")
        return redirect(url_for("admin.task_new"))

    try:
        t = TS.create_task(
            shop_id=shop.id,
            title=ftext("title", max_len=500),
            description=ftext("description", max_len=2000) or None,
            frequency=ftext("frequency", max_len=16) or "DAILY",
            weekday=fint("weekday", None),
            day_of_month=fint("day_of_month", None),
            month=fint("month", None),
            specific_date=_parse_date(ftext("specific_date", max_len=16) or None),
            task_time=ftext("task_time", max_len=8) or None,
            priority=ftext("priority", max_len=16) or "NORMAL",
        )
        audit_service.log("task.create", entity_type="task",
                          entity_id=t.id, shop_id=shop.id)
        flash("Task ကို ဖန်တီးပြီးပါပြီ။", "success")
    except ValueError as e:
        flash(str(e), "error")

    return redirect(url_for("admin.tasks_list"))


@admin_bp.route("/tasks/<int:task_id>/complete", methods=["POST"])
@login_required
def task_complete(task_id: int):
    _require(P.TASK_COMPLETE)
    note = ftext("note", max_len=1000)
    try:
        TS.update_status(task_id, "COMPLETED", note=note)
        audit_service.log("task.complete", entity_type="task", entity_id=task_id)
        flash("Task ကို Complete အဖြစ် သတ်မှတ်ပြီးပါပြီ။", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(request.referrer or url_for("admin.tasks_list"))


@admin_bp.route("/tasks/<int:task_id>/skip", methods=["POST"])
@login_required
def task_skip(task_id: int):
    _require(P.TASK_COMPLETE)
    note = ftext("note", max_len=1000)
    try:
        TS.update_status(task_id, "SKIPPED", note=note)
        flash("Task ကို Skip လုပ်လိုက်ပါပြီ။", "info")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(request.referrer or url_for("admin.tasks_list"))


# ================================================================
# Reports
# ================================================================
from app.services import report_service as RS
from app.ingestion import report_ingestor as RI
from app.models import WorkReport


@admin_bp.route("/reports")
@login_required
def reports_list():
    _require(P.REPORT_VIEW)

    shop_code = request.args.get("shop", "").strip().upper() or None
    status = request.args.get("status", "").strip().upper() or None
    q = request.args.get("q", "").strip()

    shop = get_shop_by_code(shop_code) if shop_code else None

    reports = RS.list_reports(
        shop_id=shop.id if shop else None,
        status=status or None,
        q=q or None,
    )

    return render_template(
        "admin/reports.html",
        reports=reports, shops=list_shops(),
        current_shop=shop_code or "", current_status=status or "", q=q,
    )


@admin_bp.route("/reports/new", methods=["GET", "POST"])
@login_required
def report_new():
    _require(P.REPORT_CREATE)

    if request.method == "POST":
        shop = get_shop_by_code(ftext("shop", max_len=16))
        if not shop:
            flash("ဆိုင်ကုဒ် မှန်ကန်စွာ ရွေးပါ။", "error")
            return render_template("admin/report_form.html",
                                   shops=list_shops(), mode="input")

        raw_text = ftext("raw_text", max_len=8000)

        # Save path (from preview)
        if ftext("save_action", max_len=16) == "1":
            date_s = ftext("report_date", max_len=16)
            rd = _parse_date(date_s)
            if not rd:
                flash("ရက်စွဲ မမှန်ကန်ပါ။ (YYYY-MM-DD)", "error")
                return redirect(url_for("admin.report_new"))

            # Parse metrics from form fields
            metrics: dict[str, float] = {}
            for k, v in request.form.items():
                if k.startswith("metric_key_"):
                    idx = k[len("metric_key_"):]
                    key = (v or "").strip()
                    val_s = request.form.get(f"metric_val_{idx}", "")
                    if not key:
                        continue
                    try:
                        metrics[key] = float(val_s)
                    except ValueError:
                        continue

            try:
                r = RS.create_report(
                    shop_id=shop.id,
                    report_date=rd,
                    title=ftext("title", max_len=500) or None,
                    metrics=metrics or None,
                    notes=ftext("notes", max_len=4000) or None,
                    original_content=raw_text or None,
                    status="PENDING",
                    source_type="paste",
                )
                audit_service.log("report.create", entity_type="report",
                                  entity_id=r.id, shop_id=shop.id)
                flash("Report ကို PENDING အဖြစ် သိမ်းပြီးပါပြီ။", "success")
                return redirect(url_for("admin.reports_list"))
            except ValueError as e:
                flash(str(e), "error")
                return redirect(url_for("admin.report_new"))

        # Parse path
        if raw_text:
            parsed = RI.parse(raw_text)
            return render_template(
                "admin/report_form.html",
                shops=list_shops(), mode="preview",
                shop=shop, parsed=parsed, raw_text=raw_text,
            )

        flash("စာသား paste လုပ်ပါ။", "error")
        return render_template("admin/report_form.html",
                               shops=list_shops(), mode="input")

    return render_template("admin/report_form.html",
                           shops=list_shops(), mode="input")


@admin_bp.route("/reports/<int:report_id>")
@login_required
def report_detail(report_id: int):
    _require(P.REPORT_VIEW)
    r = RS.get_report(report_id)
    if not r or r.is_deleted:
        abort(404)
    metrics = RS.metrics_of(r)
    return render_template("admin/report_detail.html", report=r, metrics=metrics)


@admin_bp.route("/reports/<int:report_id>/approve", methods=["POST"])
@login_required
def report_approve(report_id: int):
    _require(P.REPORT_EDIT)
    try:
        RS.approve_report(report_id)
        audit_service.log("report.approve", entity_type="report",
                          entity_id=report_id)
        flash("Report ကို Approve လုပ်ပြီးပါပြီ။", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.report_detail", report_id=report_id))


@admin_bp.route("/reports/compare", methods=["GET"])
@login_required
def reports_compare():
    _require(P.REPORT_VIEW)

    a_id = request.args.get("a", type=int)
    b_id = request.args.get("b", type=int)
    shop_code = request.args.get("shop", "").strip().upper() or None
    shop = get_shop_by_code(shop_code) if shop_code else None

    a = RS.get_report(a_id) if a_id else None
    b = RS.get_report(b_id) if b_id else None
    comparison = None
    if a and b:
        comparison = RS.compare_reports(a, b)

    # Suggest defaults: latest two reports for the shop
    reports_for_picker = []
    if shop:
        reports_for_picker = RS.list_reports(shop_id=shop.id, limit=50)

    return render_template(
        "admin/report_compare.html",
        a=a, b=b, comparison=comparison,
        shops=list_shops(), current_shop=shop_code or "",
        reports=reports_for_picker,
    )


# ================================================================
# Telegram Users + Admin Users
# ================================================================
from app.models import TelegramUser, TelegramUserShop


@admin_bp.route("/users")
@login_required
def users_list():
    _require(P.USER_VIEW)
    users = User.query.filter(User.is_deleted.is_(False)).order_by(User.id).all()
    return render_template("admin/users.html", users=users, roles=Role.ALL)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
def user_new():
    _require(P.USER_CREATE)

    if request.method == "POST":
        username = ftext("username", max_len=64)
        password = ftext("password", max_len=256)
        email = ftext("email", max_len=255) or None
        full_name = ftext("full_name", max_len=255) or None
        role = ftext("role", max_len=32) or "VIEWER"

        if not username or not password:
            flash("Username နဲ့ Password လိုပါတယ်။", "error")
        elif role not in Role.ALL:
            flash("Role မမှန်ကန်ပါ။", "error")
        elif User.query.filter_by(username=username).first():
            flash("Username ထပ်နေပါတယ်။", "error")
        elif len(password) < 8:
            flash("Password အနည်းဆုံး ၈ လုံး ဖြစ်ရမယ်။", "error")
        else:
            u = User(
                username=username, email=email,
                full_name=full_name, role=role, is_active=True,
            )
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            audit_service.log("user.create", entity_type="user",
                              entity_id=u.id, details={"role": role})
            flash(f"User '{username}' ဖန်တီးပြီးပါပြီ။", "success")
            return redirect(url_for("admin.users_list"))

    return render_template("admin/user_form.html", mode="new", roles=Role.ALL)


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def user_edit(user_id: int):
    _require(P.USER_EDIT)
    u = db.session.get(User, user_id)
    if not u:
        abort(404)

    if request.method == "POST":
        role = ftext("role", max_len=32) or u.role
        full_name = ftext("full_name", max_len=255) or None
        email = ftext("email", max_len=255) or None
        new_password = ftext("password", max_len=256)

        # Guard: cannot demote self out of SUPER_ADMIN if you are the only one
        if u.role == Role.SUPER_ADMIN and role != Role.SUPER_ADMIN:
            super_count = User.query.filter_by(role=Role.SUPER_ADMIN, is_active=True).count()
            if super_count <= 1:
                flash("SUPER_ADMIN တစ်ခုတည်းကို ဖျက်/ပြောင်း လို့မရပါ။", "error")
                return redirect(url_for("admin.user_edit", user_id=u.id))

        if role in Role.ALL:
            u.role = role
        u.full_name = full_name
        u.email = email
        if new_password:
            if len(new_password) < 8:
                flash("Password အနည်းဆုံး ၈ လုံး။", "error")
                return redirect(url_for("admin.user_edit", user_id=u.id))
            u.set_password(new_password)
        db.session.commit()
        audit_service.log("user.update", entity_type="user", entity_id=u.id)
        flash("User ပြင်ပြီးပါပြီ။", "success")
        return redirect(url_for("admin.users_list"))

    return render_template("admin/user_form.html", mode="edit", roles=Role.ALL, user=u)


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
def user_toggle(user_id: int):
    _require(P.USER_DISABLE)
    u = db.session.get(User, user_id)
    if not u:
        abort(404)
    if u.id == current_user.id:
        flash("မိမိကိုယ်ကို ပိတ်လို့မရပါ။", "error")
        return redirect(url_for("admin.users_list"))
    if u.role == Role.SUPER_ADMIN:
        super_count = User.query.filter_by(role=Role.SUPER_ADMIN, is_active=True).count()
        if super_count <= 1:
            flash("SUPER_ADMIN တစ်ခုတည်းကို ပိတ်လို့မရပါ။", "error")
            return redirect(url_for("admin.users_list"))

    u.is_active = not u.is_active
    db.session.commit()
    audit_service.log(
        "user.disable" if not u.is_active else "user.enable",
        entity_type="user", entity_id=u.id,
    )
    flash("User status ပြောင်းပြီးပါပြီ။", "info")
    return redirect(url_for("admin.users_list"))


# ----------------------------------------------------------------
# Telegram Users
# ----------------------------------------------------------------
@admin_bp.route("/telegram-users")
@login_required
def telegram_users_list():
    _require(P.USER_VIEW)

    users = TelegramUser.query.filter(
        TelegramUser.is_deleted.is_(False)
    ).order_by(TelegramUser.id.desc()).all()

    # Precompute shop codes per user
    user_shop_codes: dict[int, list[str]] = {}
    for u in users:
        links = TelegramUserShop.query.filter_by(
            telegram_user_id=u.id, is_active=True
        ).all()
        user_shop_codes[u.id] = [lk.shop.code for lk in links if lk.shop]

    return render_template(
        "admin/telegram_users.html",
        users=users, user_shop_codes=user_shop_codes,
    )


@admin_bp.route("/telegram-users/<int:tg_user_id>")
@login_required
def telegram_user_detail(tg_user_id: int):
    _require(P.USER_VIEW)
    u = db.session.get(TelegramUser, tg_user_id)
    if not u or u.is_deleted:
        abort(404)
    links = TelegramUserShop.query.filter_by(telegram_user_id=u.id).all()
    linked_codes = [lk.shop.code for lk in links if lk.shop]  # ★ NEW
    return render_template(
        "admin/telegram_user_detail.html",
        u=u, links=links, linked_codes=linked_codes, all_shops=list_shops(),
    )


@admin_bp.route("/telegram-users/<int:tg_user_id>/link", methods=["POST"])
@login_required
def telegram_user_link(tg_user_id: int):
    _require(P.USER_EDIT)
    u = db.session.get(TelegramUser, tg_user_id)
    if not u:
        abort(404)

    shop_code = ftext("shop_code", max_len=16).upper()
    shop = get_shop_by_code(shop_code)
    if not shop:
        flash("ဆိုင်ကုဒ် မမှန်ကန်ပါ။", "error")
        return redirect(url_for("admin.telegram_user_detail", tg_user_id=u.id))

    link = TelegramUserShop.query.filter_by(
        telegram_user_id=u.id, shop_id=shop.id
    ).first()
    if link:
        link.is_active = True
    else:
        link = TelegramUserShop(
            telegram_user_id=u.id, shop_id=shop.id, is_active=True
        )
        db.session.add(link)

    u.is_verified = True
    db.session.commit()
    audit_service.log("telegram_user.link", entity_type="telegram_user",
                      entity_id=u.id, shop_id=shop.id,
                      details={"shop": shop.code})

    # Notify user via Telegram
    all_codes = [
        lk.shop.code for lk in TelegramUserShop.query.filter_by(
            telegram_user_id=u.id, is_active=True
        ).all() if lk.shop
    ]
    try:
        resp = TN.notify_link_success(
            chat_id=u.telegram_user_id,
            shop_codes=all_codes,
            full_name=u.first_name,
        )
        if not resp.get("ok"):
            flash(f"Linked ✓ (Telegram notify failed: {resp.get('description') or resp.get('error')})", "warning")
            return redirect(url_for("admin.telegram_user_detail", tg_user_id=u.id))
    except Exception as e:
        flash(f"Linked ✓ (notify exception: {e})", "warning")
        return redirect(url_for("admin.telegram_user_detail", tg_user_id=u.id))

    flash(f"Linked to {shop.code} ✓ · Telegram message ပို့ပြီးပါပြီ", "success")
    return redirect(url_for("admin.telegram_user_detail", tg_user_id=u.id))


@admin_bp.route("/telegram-users/<int:tg_user_id>/unlink/<int:shop_id>", methods=["POST"])
@login_required
def telegram_user_unlink(tg_user_id: int, shop_id: int):
    _require(P.USER_EDIT)
    u = db.session.get(TelegramUser, tg_user_id)
    if not u:
        abort(404)
    link = TelegramUserShop.query.filter_by(
        telegram_user_id=u.id, shop_id=shop_id
    ).first()
    if not link:
        flash("Link မတွေ့ပါ။", "error")
        return redirect(url_for("admin.telegram_user_detail", tg_user_id=u.id))
    link.is_active = False
    db.session.commit()
    audit_service.log("telegram_user.unlink", entity_type="telegram_user",
                      entity_id=u.id, shop_id=shop_id)

    shop = db.session.get(Shop, shop_id)
    shop_code = shop.code if shop else "?"
    try:
        TN.notify_unlink(chat_id=u.telegram_user_id, shop_code=shop_code)
    except Exception:
        pass

    flash(f"Unlinked {shop_code} ✓", "info")
    return redirect(url_for("admin.telegram_user_detail", tg_user_id=u.id))


@admin_bp.route("/telegram-users/<int:tg_user_id>/verify", methods=["POST"])
@login_required
def telegram_user_verify(tg_user_id: int):
    _require(P.USER_EDIT)
    u = db.session.get(TelegramUser, tg_user_id)
    if not u:
        abort(404)
    u.is_verified = True
    db.session.commit()
    try:
        TN.notify_verify(chat_id=u.telegram_user_id)
    except Exception:
        pass
    flash("Verified ✓ · Telegram message ပို့ပြီးပါပြီ", "success")
    return redirect(url_for("admin.telegram_user_detail", tg_user_id=u.id))


@admin_bp.route("/telegram-users/<int:tg_user_id>/toggle-block", methods=["POST"])
@login_required
def telegram_user_toggle_block(tg_user_id: int):
    _require(P.USER_EDIT)
    u = db.session.get(TelegramUser, tg_user_id)
    if not u:
        abort(404)
    u.is_blocked = not u.is_blocked
    db.session.commit()
    audit_service.log(
        "telegram_user.block" if u.is_blocked else "telegram_user.unblock",
        entity_type="telegram_user", entity_id=u.id,
    )
    try:
        if u.is_blocked:
            TN.notify_block(chat_id=u.telegram_user_id)
        else:
            TN.notify_unblock(chat_id=u.telegram_user_id)
    except Exception:
        pass
    flash("Block status ပြောင်းပြီးပါပြီ။ (Telegram notify ပို့ပြီး)", "info")
    return redirect(url_for("admin.telegram_user_detail", tg_user_id=u.id))


# ================================================================
# Settings + Backup + Health
# ================================================================
from app.services import settings_service as SS
from app.services import backup_service as BS_BACKUP
from app.security import permissions as _P
import os


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    _require(_P.SETTINGS_VIEW)

    if request.method == "POST":
        _require(_P.SETTINGS_EDIT)
        updated = 0
        for item in SS.list_with_meta():
            key = item["key"]
            field_name = key.replace(".", "__")
            if item["type"] == "bool":
                new_val = field_name in request.form
            else:
                raw = request.form.get(field_name, "")
                if item["type"] == "int":
                    try: new_val = int(raw)
                    except ValueError: continue
                elif item["type"] == "float":
                    try: new_val = float(raw)
                    except ValueError: continue
                else:
                    new_val = raw
            if new_val != item["value"]:
                SS.set(key, new_val)
                updated += 1
        audit_service.log("settings.update", details={"changed": updated})
        flash(f"Settings သိမ်းပြီးပါပြီ။ ({updated} ခု ပြောင်း)", "success")
        return redirect(url_for("admin.settings_page"))

    return render_template(
        "admin/settings.html",
        items=SS.list_with_meta(),
    )


@admin_bp.route("/health")
@login_required
def health_page():
    _require(_P.SETTINGS_VIEW)

    from sqlalchemy import text
    from app.config import Config
    from app.ai.provider import is_configured as ai_ok, provider_name

    db_status = "ok"
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    # DB file size
    db_size = None
    try:
        from app.services.backup_service import _db_path
        p = _db_path()
        if p and p.is_file():
            db_size = p.stat().st_size
    except Exception:
        pass

    # Disk / counts
    counts = {}
    try:
        from app.models import (
            Knowledge, MachineCode, Machine, User,
            TelegramUser, Task, WorkReport,
        )
        counts = {
            "knowledge": Knowledge.query.filter_by(is_deleted=False).count(),
            "machine_codes": MachineCode.query.count(),
            "machines": Machine.query.filter_by(is_deleted=False).count(),
            "users": User.query.filter_by(is_deleted=False).count(),
            "telegram_users": TelegramUser.query.filter_by(is_deleted=False).count(),
            "tasks": Task.query.filter_by(is_deleted=False).count(),
            "reports": WorkReport.query.filter_by(is_deleted=False).count(),
        }
    except Exception:
        pass

    return render_template(
        "admin/health.html",
        db_status=db_status,
        db_size=db_size,
        counts=counts,
        ai_configured=ai_ok(),
        ai_provider=provider_name(),
        telegram_configured=bool(Config.TELEGRAM_BOT_TOKEN),
        telegram_enabled=Config.TELEGRAM_ENABLED,
        site_name=SS.get("system.site_name"),
    )


@admin_bp.route("/backups")
@login_required
def backups_list():
    _require(_P.SETTINGS_VIEW)
    backups = BS_BACKUP.list_backups()
    return render_template("admin/backup.html", backups=backups)


@admin_bp.route("/backups/create", methods=["POST"])
@login_required
def backups_create():
    _require(_P.SETTINGS_EDIT)
    label = ftext("label", max_len=64) or None
    try:
        p = BS_BACKUP.create_backup(label=label)
        audit_service.log("backup.create", details={"file": p.name})
        flash(f"Backup ဖန်တီးပြီးပါပြီ: {p.name}", "success")
    except Exception as e:
        flash(f"Backup fail: {e}", "error")
    return redirect(url_for("admin.backups_list"))


@admin_bp.route("/backups/<name>/restore", methods=["POST"])
@login_required
def backups_restore(name: str):
    _require(_P.SETTINGS_EDIT)
    if not name.startswith("backup_") or "/" in name or ".." in name:
        abort(400)
    try:
        res = BS_BACKUP.restore_backup(name, confirm=True)
        if res.get("ok"):
            audit_service.log("backup.restore", details=res)
            flash(f"Restore အောင်မြင်ပါပြီ။ Server ကို restart လုပ်ပါ။", "success")
        else:
            flash(f"Restore fail: {res.get('error')}", "error")
    except Exception as e:
        flash(f"Restore fail: {e}", "error")
    return redirect(url_for("admin.backups_list"))


@admin_bp.route("/backups/<name>/delete", methods=["POST"])
@login_required
def backups_delete(name: str):
    _require(_P.SETTINGS_EDIT)
    if not name.startswith("backup_") or "/" in name or ".." in name:
        abort(400)
    BS_BACKUP.delete_backup(name)
    audit_service.log("backup.delete", details={"file": name})
    flash("Backup ဖျက်ပြီးပါပြီ။", "info")
    return redirect(url_for("admin.backups_list"))


@admin_bp.route("/backups/<name>/download")
@login_required
def backups_download(name: str):
    _require(_P.SETTINGS_VIEW)
    if not name.startswith("backup_") or "/" in name or ".." in name:
        abort(400)
    from flask import send_file
    from app.services.backup_service import BACKUP_DIR
    p = BACKUP_DIR / name
    if not p.is_file():
        abort(404)
    return send_file(str(p), as_attachment=True, download_name=name)


# ================================================================
# Late imports (safety net for PART 15/19/20/22)
# These are used by ingest/image/media/knowledge routes.
# ================================================================
from app.services import file_service as FS2  # noqa: E402,F401,F811
from app.services import media_service as MS  # noqa: E402,F401,F811
from app.services import knowledge_service as KS  # noqa: E402,F401,F811
from app.models import KnowledgeStatus  # noqa: E402,F401
from app.models import MediaCategory, MediaFile  # noqa: E402,F401


# ================================================================
# Error Knowledge Excel Import (specialized)
# ================================================================
from app.ingestion import error_excel_ingestor as EEI


@admin_bp.route("/errors/import", methods=["GET", "POST"])
@login_required
def errors_import():
    """Import Error Knowledge. Admin supplies Machine Name once."""
    _require(P.ERROR_CREATE)

    if request.method == "POST":
        shop_code = ftext("shop", max_len=16)
        shop = get_shop_by_code(shop_code)
        if not shop:
            flash("ဆိုင်ကုဒ် မှန်ကန်စွာ ရွေးပါ။", "error")
            return render_template("admin/errors_import.html",
                                   shops=list_shops(), mode="input")

        # Admin-supplied machine name (applies to all rows)
        machine_name = ftext("machine_name", max_len=255)
        model = ftext("model", max_len=128)
        unit = ftext("unit", max_len=64)

        f = request.files.get("file")
        if not f or not f.filename:
            flash("Excel ဖိုင် ရွေးပါ။", "error")
            return render_template("admin/errors_import.html",
                                   shops=list_shops(), mode="input")

        try:
            meta = FS2.save_upload(f, category="excel")
        except ValueError as e:
            flash(str(e), "error")
            return render_template("admin/errors_import.html",
                                   shops=list_shops(), mode="input")

        try:
            result = EEI.read_error_excel(meta["file_path"])
        except Exception as e:
            current_app.logger.exception("Error Excel read failed: %s", e)
            flash("Excel ဖတ်လို့ မရပါ။", "error")
            return redirect(url_for("admin.errors_import"))

        # Fall back to filename-based name if Admin didn't type one
        if not machine_name:
            machine_name = result.machine_name or ""

        return render_template(
            "admin/errors_import.html",
            shops=list_shops(), mode="preview",
            shop=shop, result=result,
            machine_name=machine_name,
            model=model,
            unit=unit,
            source_filename=meta["original_filename"],
        )

    return render_template("admin/errors_import.html",
                           shops=list_shops(), mode="input")


def errors_import_save():
    _require(P.ERROR_CREATE)

    shop = get_shop_by_code(ftext("shop", max_len=16))
    if not shop:
        flash("ဆိုင်ကုဒ် မမှန်ကန်ပါ။", "error")
        return redirect(url_for("admin.errors_import"))

    default_machine = ftext("default_machine", max_len=255)
    default_model = ftext("default_model", max_len=128)
    default_unit = ftext("default_unit", max_len=64)
    source_file = ftext("source_file", max_len=512)

    selected = request.form.getlist("selected")
    if not selected:
        flash("သိမ်းလိုတဲ့ row တွေ ရွေးပါ။", "error")
        return redirect(url_for("admin.errors_import"))

    saved = 0
    for idx_s in selected:
        try:
            i = int(idx_s)
        except ValueError:
            continue

        title = ftext(f"row_{i}_title", max_len=512) or "Error"
        content = ftext(f"row_{i}_content", max_len=8000)
        error_code = ftext(f"row_{i}_error_code", max_len=64) or None
        machine_name = ftext(f"row_{i}_machine", max_len=255) or default_machine
        model = ftext(f"row_{i}_model", max_len=128) or default_model
        unit = ftext(f"row_{i}_unit", max_len=64) or default_unit

        if not content:
            continue

        try:
            ek = ES.create_error_knowledge(
                shop_id=shop.id,
                error_code=error_code,
                error_name=title[:500],
                machine_name=machine_name or None,
                model=model or None,
                unit=unit or None,
                symptoms=None,
                cause=None,
                check_steps=None,
                solution=content,
                notes=None,
                status="PENDING",
            )
            # Store source reference via update
            ek.source_type = "excel"
            ek.source_file = source_file or None
            saved += 1
        except ValueError as e:
            current_app.logger.warning("Skipped error row %s: %s", i, e)

    db.session.commit()
    audit_service.log("error_knowledge.import", entity_type="error_knowledge_bulk",
                      shop_id=shop.id,
                      details={"saved": saved, "source": source_file})
    flash(f"{saved} Error Knowledge PENDING အဖြစ် သိမ်းပြီးပါပြီ။", "success")
    return redirect(url_for("admin.errors_list", status="PENDING"))


# ================================================================
# errors_import_save (restored — was lost during PART 23 edit)
# ================================================================


# ================================================================
# Analytics Dashboard
# ================================================================
from app.services import analytics_service as AS


@admin_bp.route("/analytics")
@login_required
def analytics_dashboard():
    _require(P.DASHBOARD_VIEW)

    days = request.args.get("days", type=int, default=7)
    days = max(1, min(days, 90))

    summary = AS.summary(days=days)
    top_q = AS.top_queries(days=days, limit=15)
    top_s = AS.top_shops(days=days, limit=10)
    sources = AS.search_sources(days=days)
    daily = AS.daily_counts(days=min(days * 2, 30))
    top_ev = AS.top_events(days=days, limit=10)
    top_tg = AS.top_telegram_users(days=days, limit=10)

    return render_template(
        "admin/analytics.html",
        days=days,
        summary=summary,
        top_queries=top_q,
        top_shops=top_s,
        sources=sources,
        daily=daily,
        top_events=top_ev,
        top_telegram_users=top_tg,
    )


# ================================================================
# Knowledge Photos
# ================================================================
from app.services import knowledge_photo_service as KPS
from app.models import KnowledgePhoto


@admin_bp.route("/knowledge/<int:knowledge_id>/photos/upload", methods=["POST"])
@login_required
def knowledge_photo_upload(knowledge_id: int):
    _require(P.KNOWLEDGE_EDIT)

    f = request.files.get("photo")
    if not f or not f.filename:
        flash("ပုံ ရွေးပါ။", "error")
        return redirect(url_for("admin.knowledge_detail", knowledge_id=knowledge_id))

    caption = ftext("caption", max_len=500) or None
    try:
        KPS.add_photo(knowledge_id=knowledge_id, file=f, caption=caption)
        flash("ပုံ ထည့်ပြီးပါပြီ။", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.knowledge_detail", knowledge_id=knowledge_id))


@admin_bp.route("/knowledge/photos/<int:photo_id>/delete", methods=["POST"])
@login_required
def knowledge_photo_delete(photo_id: int):
    _require(P.KNOWLEDGE_EDIT)
    p = db.session.get(KnowledgePhoto, photo_id)
    if not p:
        abort(404)
    kid = p.knowledge_id
    KPS.delete_photo(photo_id)
    flash("ပုံ ဖျက်ပြီးပါပြီ။", "info")
    return redirect(url_for("admin.knowledge_detail", knowledge_id=kid))


@admin_bp.route("/knowledge/photos/<int:photo_id>/caption", methods=["POST"])
@login_required
def knowledge_photo_caption(photo_id: int):
    _require(P.KNOWLEDGE_EDIT)
    p = db.session.get(KnowledgePhoto, photo_id)
    if not p:
        abort(404)
    KPS.set_caption(photo_id, ftext("caption", max_len=500) or None)
    flash("Caption သိမ်းပြီးပါပြီ။", "success")
    return redirect(url_for("admin.knowledge_detail", knowledge_id=p.knowledge_id))


@admin_bp.route("/knowledge/photos/<int:photo_id>/view")
@login_required
def knowledge_photo_view(photo_id: int):
    """Serve a knowledge photo (auth required)."""
    _require(P.KNOWLEDGE_VIEW)
    p = db.session.get(KnowledgePhoto, photo_id)
    if not p or not p.file_path:
        abort(404)
    from flask import send_file
    return send_file(p.file_path, mimetype=p.mime_type or "image/jpeg")


# ================================================================
# Admin Broadcast (chat box → verified Telegram users)
# ================================================================
from app.services import broadcast_service as BS_BROADCAST
from app.models import Broadcast, BroadcastRecipient


@admin_bp.route("/broadcast", methods=["GET", "POST"])
@login_required
def broadcast_page():
    _require(P.SETTINGS_VIEW)

    if request.method == "POST":
        _require(P.SETTINGS_EDIT)

        message = ftext("message", max_len=4000)
        shop_code = ftext("shop", max_len=16).upper() or None
        shop = get_shop_by_code(shop_code) if shop_code else None

        # ★ Multi-photo
        photos = request.files.getlist("photos")
        photos = [f for f in photos if f and f.filename]
        # Cap at 10
        photos = photos[:10]

        try:
            b = BS_BROADCAST.create_broadcast(
                message=message,
                photos=photos,
                shop_id=shop.id if shop else None,
            )
            result = BS_BROADCAST.send_broadcast(b.id)
            flash(
                f"Broadcast ပို့ပြီးပါပြီ — ✓ {result.get('sent', 0)} / "
                f"✗ {result.get('failed', 0)} (total {result.get('total', 0)})",
                "success",
            )
            return redirect(url_for("admin.broadcast_detail", bid=b.id))
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("admin.broadcast_page"))

    all_count = len(BS_BROADCAST.get_recipients())
    return render_template(
        "admin/broadcast.html",
        all_count=all_count,
        shops=list_shops(),
        history=BS_BROADCAST.list_broadcasts(limit=20),
    )


@admin_bp.route("/broadcast/<int:bid>")
@login_required
def broadcast_detail(bid: int):
    _require(P.SETTINGS_VIEW)
    b = BS_BROADCAST.get_broadcast(bid)
    if not b:
        abort(404)
    return render_template("admin/broadcast_detail.html", b=b)


@admin_bp.route("/broadcast/photos/<int:pid>/view")
@login_required
def broadcast_photo_view(pid: int):
    """Serve a broadcast photo (auth required)."""
    _require(P.SETTINGS_VIEW)
    from app.models import BroadcastPhoto
    p = db.session.get(BroadcastPhoto, pid)
    if not p or not p.file_path:
        abort(404)
    from flask import send_file
    return send_file(p.file_path, mimetype=p.mime_type or "image/jpeg")


# ================================================================
# Telegram Groups + Topics
# ================================================================
from app.services import telegram_group_service as TGS
from app.models import TelegramGroupConfig


@admin_bp.route("/telegram-groups")
@login_required
def telegram_groups_list():
    _require(P.USER_VIEW)
    groups = TGS.list_groups(only_enabled=False)
    return render_template("admin/telegram_groups.html", groups=groups)


@admin_bp.route("/telegram-groups/parse", methods=["POST"])
@login_required
def telegram_groups_parse():
    """Parse a link, register the group (no thread yet)."""
    _require(P.USER_EDIT)
    link = ftext("link", max_len=500)
    chat_id, thread_id = TGS.parse_group_link(link)

    if not chat_id:
        flash("Link မမှန်ကန်ပါ။ ဥပမာ: https://t.me/c/1234567890/5", "error")
        return redirect(url_for("admin.telegram_groups_list"))

    cfg = TGS.register_or_update(
        chat_id=chat_id,
        allowed_thread_ids=[thread_id] if thread_id else [],
    )
    audit_service.log("telegram_group.register", entity_type="telegram_group",
                      entity_id=cfg.id, details={"chat_id": chat_id, "thread": thread_id})
    flash(f"Group registered: {chat_id}" + (f" (topic {thread_id})" if thread_id else ""),
          "success")
    return redirect(url_for("admin.telegram_group_detail", chat_id=chat_id))


@admin_bp.route("/telegram-groups/<chat_id>")
@login_required
def telegram_group_detail(chat_id: str):
    try:
        chat_id = int(chat_id)
    except ValueError:
        abort(404)
    _require(P.USER_VIEW)
    g = TGS.get_by_chat_id(chat_id)
    if not g:
        abort(404)
    return render_template("admin/telegram_group_detail.html", group=g)


@admin_bp.route("/telegram-groups/<chat_id>/edit", methods=["POST"])
@login_required
def telegram_group_edit(chat_id: str):
    try:
        chat_id = int(chat_id)
    except ValueError:
        abort(404)
    _require(P.USER_EDIT)
    g = TGS.get_by_chat_id(chat_id)
    if not g:
        abort(404)

    # Parse thread IDs from textarea (one per line or comma separated)
    raw = ftext("threads", max_len=2000)
    threads: list[int] = []
    for line in (raw or "").replace(",", "\n").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            try:
                threads.append(int(s))
            except ValueError:
                pass

    TGS.set_options(
        chat_id=chat_id,
        allowed_thread_ids=threads,
        reply_in_thread=("reply_in_thread" in request.form),
        require_mention=("require_mention" in request.form),
    )
    audit_service.log("telegram_group.update", entity_type="telegram_group",
                      entity_id=g.id)
    flash("Group config သိမ်းပြီးပါပြီ။", "success")
    return redirect(url_for("admin.telegram_group_detail", chat_id=chat_id))


@admin_bp.route("/telegram-groups/<chat_id>/toggle", methods=["POST"])
@login_required
def telegram_group_toggle(chat_id: str):
    try:
        chat_id = int(chat_id)
    except ValueError:
        abort(404)
    _require(P.USER_EDIT)
    g = TGS.get_by_chat_id(chat_id)
    if not g:
        abort(404)
    TGS.set_enabled(chat_id, not g.is_enabled)
    flash("Status ပြောင်းပြီးပါပြီ။", "info")
    return redirect(url_for("admin.telegram_group_detail", chat_id=chat_id))


@admin_bp.route("/telegram-groups/<chat_id>/remove", methods=["POST"])
@login_required
def telegram_group_remove(chat_id: str):
    try:
        chat_id = int(chat_id)
    except ValueError:
        abort(404)
    _require(P.USER_EDIT)
    if TGS.remove(chat_id):
        flash("Group removed.", "info")
    return redirect(url_for("admin.telegram_groups_list"))


# ================================================================
# Live Monitor
# ================================================================
@admin_bp.route("/live")
@login_required
def live_monitor():
    """Live system monitor page."""
    return render_template("admin/live.html")


@admin_bp.route("/api/admin/live")
@login_required
def api_live_status():
    """Live status JSON — for auto-refresh."""
    from datetime import datetime, timedelta
    from app.extensions import db
    from app.models import TelegramUser, TelegramUserShop, Shop, Task, TaskHistory
    from app.models.bot_activity import BotActivity

    now = datetime.now()
    cutoff_30 = now - timedelta(minutes=30)

    # Active users (last 30 min)
    active_users = TelegramUser.query.filter(
        TelegramUser.is_verified == True,  # noqa: E712
        TelegramUser.is_blocked == False,  # noqa: E712
    ).count()

    # Users seen in last 30 min (via activity)
    active_30m = db.session.query(
        db.func.count(db.distinct(BotActivity.telegram_user_id))
    ).filter(BotActivity.created_at >= cutoff_30).scalar() or 0

    # Shops + user count
    shops = db.session.query(
        Shop.code,
        db.func.count(db.distinct(TelegramUserShop.telegram_user_id)),
    ).outerjoin(
        TelegramUserShop, TelegramUserShop.shop_id == Shop.id,
    ).group_by(Shop.code).all()
    shops_data = [{"code": c, "users": int(n or 0)} for c, n in shops if n]

    # Tasks
    active_tasks = Task.query.filter_by(
        status="PENDING", is_deleted=False
    ).count()
    today = now.date()
    sent_today = TaskHistory.query.filter(
        TaskHistory.status == "SENT",
        db.func.date(TaskHistory.created_at) == today,
    ).count()

    # Processes (ps)
    import subprocess
    try:
        ps_out = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=5
        ).stdout
    except Exception:
        ps_out = ""
    bot_ok = "python bot.py" in ps_out
    flask_ok = "python run.py" in ps_out
    watchdog_ok = "watchdog.sh" in ps_out

    # Recent activity (20)
    recent = BotActivity.query.order_by(
        BotActivity.created_at.desc()
    ).limit(20).all()

    recent_data = [{
        "id": r.id,
        "user_id": r.telegram_user_id,
        "first_name": r.first_name or "—",
        "shop_code": r.shop_code or "—",
        "activity_type": r.activity_type or "—",
        "content": (r.content or "")[:120],
        "response": (r.response or "")[:200],
        "ok": bool(r.response_ok),
        "created_at": r.created_at.strftime("%H:%M:%S") if r.created_at else "—",
    } for r in recent]

    return jsonify({
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "users": {
            "verified": active_users,
            "active_30m": active_30m,
        },
        "shops": shops_data,
        "tasks": {
            "active": active_tasks,
            "sent_today": sent_today,
        },
        "processes": {
            "bot": bot_ok,
            "flask": flask_ok,
            "watchdog": watchdog_ok,
        },
        "recent": recent_data,
    })


