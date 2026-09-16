#!/data/data/com.termux/files/usr/bin/bash
cd ~/ai_digital_brain

ROUTES=(
  dashboard shops_list audit_list
  machines_list machine_new machine_detail machine_edit
  machine_archive machine_alias_add machine_alias_remove
  machine_codes_list machine_codes_import machine_codes_import_commit
  machine_code_source_approve machine_code_approve machine_code_archive
  knowledge_list knowledge_detail knowledge_approve knowledge_archive
  teach_quick teach_quick_save
  knowledge_conflicts knowledge_conflict_resolve
  errors_list error_new error_edit error_approve
  error_cases_list error_case_new error_case_approve
  files_list files_upload file_detail file_download file_delete
  ingest_document_page ingest_document_save
  search_page image_ingest image_ingest_save
  ai_test
)

MISSING=0
DUPLICATE=0
OK=0

for r in "${ROUTES[@]}"; do
  count=$(grep -c "def ${r}(" app/routes/admin.py)
  if [ "$count" -eq 0 ]; then
    echo "❌ MISSING: $r"
    MISSING=$((MISSING+1))
  elif [ "$count" -gt 1 ]; then
    echo "⚠️  DUPLICATE ($count): $r"
    DUPLICATE=$((DUPLICATE+1))
  else
    OK=$((OK+1))
  fi
done

echo
echo "================="
echo "OK:        $OK"
echo "Missing:   $MISSING"
echo "Duplicate: $DUPLICATE"
