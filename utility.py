import json
import datetime
import random
def read_json(file:str):
    try:
        with open(file=file,mode="r",encoding="UTF-8") as f:
                data = f.read()
                f.close()
        return json.loads(data)
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


def add_sube(file:str,espacio:int,subespacios:list[dict]):
    a = read_json(file)
    
    for subespacio in subespacios:
        a["Espacios"][espacio]["Subespacios"].append(subespacio)

    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(a,f,indent=1,ensure_ascii=False)
        f.close()

def mod_sube(file:str,espacio:int,subespacio_id:int,clones:bool):
    a = read_json(file)
    
    a["Espacios"][espacio]["Subespacios"][subespacio_id]["Clones"] = clones

    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(a,f,indent=1,ensure_ascii=False)
        f.close()


def add_plant(file:str,espacio:int,subespacio:int,var_id:int,indiv:dict):
    a = read_json(file)
    
    a["Espacios"][espacio]["Subespacios"][subespacio]["Individuos"].append(indiv)
    sub_id = a["Espacios"][espacio]["Subespacios"][subespacio]["ID"]    
    a["Variedades"][var_id]["indivs"].append({"ID":indiv["ID"],"loc":sub_id})

    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(a,f,indent=1,ensure_ascii=False)
        f.close()


def add_log(file:str,logs:list[dict]):
    a = read_json(file)
    
    for log in logs:
        a["Logs"].append(log)

    #TODO sort logs by date
    
    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(a,f,indent=1,ensure_ascii=False)
        f.close()


def mod_plant(file:str,plants:list[dict],sube:str=None,estadio:str=None,size:str=None):
    a = read_json(file)
    
    for plant in plants:
        curr_loc_id = None 
        var_idx = get_var_id(plant["ID"])
        var_j = -1
        for i in range(len(a["Variedades"])):
            var = a["Variedades"][i]
            if var["Nombre"] == var_idx[0]:
                var_j = i
                curr_loc_id = var["indivs"][var_idx[1]]["loc"]
                break
            
            
        loc_id = get_loc_idx(curr_loc_id)
        curr_sube = a["Espacios"][loc_id[0]]["Subespacios"][loc_id[1]]  
        plant_idx = -1
        for i in range(len(curr_sube["Individuos"])):
            if curr_sube["Individuos"][i]["ID"] == plant["ID"]:
                plant_idx = i
                break
            
        if sube is not None and sube != curr_sube["ID"]:
            a["Espacios"][loc_id[0]]["Subespacios"][loc_id[1]]["Individuos"].pop(plant_idx)
            new_loc_id = get_loc_idx(sube)
            a["Espacios"][new_loc_id[0]]["Subespacios"][new_loc_id[1]]["Individuos"].append(plant)
            a["Variedades"][var_j]["indivs"][var_idx[1]]["loc"] = sube
        if estadio is not None:
            a["Espacios"][loc_id[0]]["Subespacios"][loc_id[1]]["Individuos"][plant_idx]["Estadio"] = estadio

        if size is not None:
            a["Espacios"][loc_id[0]]["Subespacios"][loc_id[1]]["Individuos"][plant_idx]["Tam"] = size


    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(a,f,indent=1,ensure_ascii=False)
        f.close()


def delete(file:str,type:str,id:int=None,type2:str=None,idx2:int=None):
    a = read_json(file)

    if type2 is None:a[type].pop(id)
    else: 
        if id is not None:a[type][id][type2].pop(idx2)
        else: a[type][type2].pop(idx2)

    with open(file=file,mode="w",encoding="UTF-8") as f:
        json.dump(a,f,indent=1,ensure_ascii=False)
        f.close()




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



