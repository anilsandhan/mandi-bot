lines = []
with open(r"C:\mandi_bot\.env", "r") as f:
    for line in f:
        if not line.startswith("DATABASE_URL"):
            lines.append(line)

new_url = "DATABASE_URL=postgresql://postgres:Sandhan%402021@db.loflxnrbalaamtzdpdtf.supabase.co:5432/postgres\n"
lines.append(new_url)

with open(r"C:\mandi_bot\.env", "w", newline="\n") as f:
    f.writelines(lines)

print("Done -- new DATABASE_URL written")