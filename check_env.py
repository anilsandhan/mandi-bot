f = open(r"C:\mandi_bot\.env", "r")
for line in f:
    if "DATABASE" in line:
        print(repr(line))