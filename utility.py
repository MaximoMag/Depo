import json
import datetime
import random
from firebase_admin import db


def read_json(file:str):
    try:
        with open(file=file,mode="r",encoding="UTF-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.decoder.JSONDecodeError:
        return None

def add_to_db(file:str,espacios:list[dict]=None,variedades:list[dict]=None,prods:list[tuple[str,str]]=None,tams:list[str]=None,ests:list[str]=None):
    a = read_json(file)
    
    if espacios is not None:
        for espacio in espacios:
            a["Espacios"].append(espacio)
    
    if variedades is not None:
        for var in variedades:
            a["Variedades"].append(var)
    
    if prods is not None:
        for prod in prods:
            a["Productos"][f"{prod[1]}"].append(prod[0])

    if tams is not None:
        for tam in tams:
            a["Tams"].append(tam)

    if ests is not None:
        for est in ests:
            a["Estadios"].append(est)


    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(a,f,indent=1,ensure_ascii=False)
        f.close()

def add_to_fdb(db,espacios:list[dict]=None,variedades:list[dict]=None,prods:list[tuple[str,str]]=None,tams:list[str]=None,ests:list[str]=None):
    if espacios is not None:
        ref = db.reference(f"/Espacios/")
        old = ref.get() 
        if old is None:old = []
        ref.set(old + espacios)
            
    
    if variedades is not None:
        ref = db.reference(f"/Variedades/")
        old = ref.get() 
        if old is None:old = []
        ref.set(old + variedades)


    if prods is not None:    
        p_rr = db.reference("/Productos/prods_r/")
        p_pr = db.reference("/Productos/prods_p/")
        p_hr = db.reference("/Productos/prods_h/")

        old_pr = p_rr.get()
        old_pp = p_pr.get()
        old_ph = p_hr.get()

        if old_pp is None: old_pp = []
        if old_ph is None: old_ph = []
        if old_pr is None: old_pr = []

        p_r = []
        p_p = []
        p_h = []

        for prod in prods:
            if prod[1] == "prods_r":p_r.append(prod[0])
            elif prod[1] == "prods_p":p_p.append(prod[0])
            else:p_h.append(prod[0])

        if p_r: p_rr.set(old_pr + p_r)
        if p_p: p_pr.set(old_pp + p_p)
        if p_h: p_hr.set(old_ph + p_h)

    if tams is not None:
        ref = db.reference(f"/Tams/")
        old = ref.get() 
        if old is None:old = []
        ref.set(old + tams)

    if ests is not None:
        ref = db.reference(f"/Estadios/")
        old = ref.get() 
        if old is None:old = []
        ref.set(old + ests)

def add_sube(file:str,espacio:int,subespacios:list[dict]):
    a = read_json(file)
    
    for subespacio in subespacios:
        a["Espacios"][espacio]["Subespacios"].append(subespacio)

    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(a,f,indent=1,ensure_ascii=False)
        f.close()

def add_sube_fdb(db,espacio:int,subespacios:list[dict]):
    ref = db.reference(f"Espacios/{espacio}/Subespacios/")
    old = ref.get() 
    if old is None:old = []
    ref.set(old + subespacios)

def mod_sube(file:str,espacio:int,subespacio_id:int,clones:bool):
    a = read_json(file)
    
    a["Espacios"][espacio]["Subespacios"][subespacio_id]["Clones"] = clones

    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(a,f,indent=1,ensure_ascii=False)
        f.close()

def mod_sube_fdb(db,espacio:int,sube_id:int,clones:bool):
    db.reference(f"/Espacios/{espacio}/Subespacios/{sube_id}").update({"Clones":clones})

def add_plant(file:str,espacio:int,subespacio:int,var_id:int,indiv:dict):
    a = read_json(file)
    
    a["Espacios"][espacio]["Subespacios"][subespacio]["Individuos"].append(indiv)
    sub_id = a["Espacios"][espacio]["Subespacios"][subespacio]["ID"]    
    a["Variedades"][var_id]["Individuos"].append({"ID":indiv["ID"],"Loc":sub_id})

    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(a,f,indent=1,ensure_ascii=False)
        f.close()

def add_planta_fdb(db,espacio:int,sube:int,var_id:int,indivs:list[dict]):
    sub_id = "E-" + str(espacio) + "S-" + str(sube)
    vars = [{"ID":indiv["ID"],"Loc":sub_id} for indiv in indivs]     
    ref = db.reference(f"/Espacios/{espacio}/Subespacios/{sube}/Individuos/")
    old = ref.get() 
    if old is None:old = []
    ref.set(old + indivs)
    
    ref = db.reference(f"/Variedades/{var_id}/Individuos/")
    old = ref.get() 
    if old is None:old = []
    ref.set(old + vars)

def add_log(file:str,logs:list[dict]):
    a = read_json(file)
    
    for log in logs:
        a["Logs"].append(log)

    #TODO sort logs by date
    
    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(a,f,indent=1,ensure_ascii=False)
        f.close()

def add_log_fbd(db,logs:list[dict]):
    db.reference(f"/Logs").push(logs)

def mod_plant(file:str,plants:list[dict],sube:str=None,estadio:str=None,size:str=None):
    #TODO update method based in fbd method
    a = read_json(file)
    
    for plant in plants:
        curr_loc_id = None 
        var_idx = get_var_id(plant["ID"])
        var_j = -1
        for i in range(len(a["Variedades"])):
            var = a["Variedades"][i]
            if var["Nombre"] == var_idx[0]:
                var_j = i
                curr_loc_id = var["Individuos"][var_idx[1]]["Loc"]
                break
            
            
        loc_id = get_loc_idx(curr_loc_id)
        curr_sube = a["Espacios"][loc_id[0]]["Subespacios"][loc_id[1]]  
        plant_idx = -1
        for i in range(len(curr_sube["Individuos"])):
            if curr_sube["Individuos"][i]["ID"] == plant["ID"]:
                plant_idx = i
                break
            
        if sube is not None and sube != curr_sube["ID"]:
            if estadio is not None: plant["Estadio"] = estadio
            if size is not None: plant["Tam"] = size

            a["Espacios"][loc_id[0]]["Subespacios"][loc_id[1]]["Individuos"].pop(plant_idx)
            new_loc_id = get_loc_idx(sube)
            a["Espacios"][new_loc_id[0]]["Subespacios"][new_loc_id[1]]["Individuos"].append(plant)
            a["Variedades"][var_j]["Individuos"][var_idx[1]]["Loc"] = sube


        elif estadio is not None:
            a["Espacios"][loc_id[0]]["Subespacios"][loc_id[1]]["Individuos"][plant_idx]["Estadio"] = estadio

        elif size is not None:
            a["Espacios"][loc_id[0]]["Subespacios"][loc_id[1]]["Individuos"][plant_idx]["Tam"] = size


    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(a,f,indent=1,ensure_ascii=False)
        f.close()

def mod_plant_fbd(db,plantas:list[dict],sube:str=None,estadio:str=None,size:str=None,locations:list=[],var_locations:list=[]):
    if sube is not None:
        new_loc_id = get_loc_idx(sube)
        new_loc_ref = db.reference(f"/Espacios/{new_loc_id[0]}/Subespacios/{new_loc_id[1]}/Individuos/")
        old = new_loc_ref.get()
        old = [] if old is None else old
        old += plantas
        new_loc_ref.set(old)

        for i in range(plantas):
            p_var = get_var_id(plantas[i]["ID"])
            ref = db.reference(f"/Espacios/{locations[i][0]}/Subespacios/{locations[i][1]}/Individuos/")
            ref.child(locations[i][2]).delete()
            old = ref.get()
            ref.set(old)
            db.reference(f"/Variedades/{var_locations[i]}/Individuos/{p_var[1]}").update({"Loc":sube})


    for i in range(len(plantas)):
        if estadio is not None:db.reference(f"/Espacios/{locations[i][0]}/Subespacios/{locations[i][1]}/Individuos/{locations[i][2]}").update({"Est":estadio})
        if size is not None:db.reference(f"/Espacios/{locations[i][0]}/Subespacios/{locations[i][1]}/Individuos/{locations[i][2]}").update({"Tam":size})
    
def delete(file:str,type:str,id:int=None,type2:str=None,idx2:int=None):
    a = read_json(file)

    if type2 is None:
        if type != "Espacios":a[type].pop(id)
        else: a[type]["Existe"] = False
    else: 
        if id is not None:
            if type != "Espacios":a[type][id][type2].pop(idx2)
            else: [type][id][type2]["Existe"] = False
        else: a[type][type2].pop(idx2)

    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(a,f,indent=1,ensure_ascii=False)
        f.close()

def delete_fdb(db,type:str,id:int=None,type2:str=None,idx2:int=None):
    if type2 is None:
        if type != "Espacios":
            ref = db.reference(f"/{type}")
            old_ = ref.get()
            old_.pop(id)
            ref.set(old_)

        else:db.reference(f"/{type}/{id}").update({"Existe":False})
    else: 
        if id is not None:
            if type != "Espacios":db.reference(f"/{type}/{id}/{type2}/{idx2}").delete()
            else: db.reference(f"/{type}/{id}/{type2}/{idx2}").update({"Existe":False})
        else: 
            ref = db.reference(f"/{type}/{type2}")
            old_ = ref.get()
            old_.pop(idx2)
            ref.set(old_)

def get_loc_idx(id:str) -> tuple[int,int]: #[0] = id espacio| [1] = id subespacio
    e_idx = 2
    s_idx = id.index("S") if "S" in id else len(id)
    a = int(id[e_idx:s_idx]) if id[e_idx:s_idx].isnumeric() else -1
    b = int(id[s_idx+2:]) if id[s_idx+2:].isnumeric() else -1
    return [a,b] 

def get_var_id(id:str) -> tuple[str,int]:#[0] = nombre variante | [1] = id variante
    idx = id.index("-")
    a = str(id[:idx])
    b = int(id[idx+1:])
    return [a,b]

def create_db(file,base):
    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(base,f,indent=1,ensure_ascii=False)
        f.close()