import sys
sys.path.append(r"C:/Users/HP ELITEBOOK 1030/Documents/#Mes Docs/Projet/ISMAILA/MVP 7 Pilote V3")

try:
    import views.admin_view as av
    print("import ok")
except Exception as e:
    print("import error:", e)
