from tinydb import TinyDB, Query

db              = TinyDB("db.json")
users_table     = db.table("users")
contests_table  = db.table("contests")
parts_table     = db.table("participations")
subs_table      = db.table("submissions")

User     = Query()
Contest  = Query()
Part     = Query()
