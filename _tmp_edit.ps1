 = "D:\work\exam-mistake-manager\scripts\mistake_manager.py"
 = [System.IO.File]::ReadAllText(, [System.Text.Encoding]::UTF8)

# In modify_mistake, add db.update_mistake_field before the final return card
 = "        index_manager.add_entry(card)
    return card

def get_screen_path"
 = "        index_manager.add_entry(card)
    # V3: 同步更新 SQLite
    db.update_mistake_field(mistake_id, field, value)
    return card

def get_screen_path"
 = .Replace(, )

[System.IO.File]::WriteAllText(, , [System.Text.Encoding]::UTF8)
Write-Host "Done"
