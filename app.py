import flask
import werkzeug
import json

import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

import os
from dotenv import load_dotenv
import utility
import datetime

#Riego = 0,Pulve = 1,trat_p = 2,trat_h = 3,trans = 5,poda = 4,bitacora = 6,mod move = 7,morir = 8,añadir planta = 9,cambio estadio = 10, 61 log sube, 62 log esp

class Depo():
    def __init__(self,debug:bool):
        self.app = flask.Flask(__name__)
        self.debug = debug
        load_dotenv()
        self.app.secret_key = os.getenv("f_key")

        if debug:
            self.file = os.path.dirname(__file__) + "\\database\\db.json"
            self.db = utility.read_json(self.file)
            if self.db is None: self.db = {"Espacios":[],"Productos":{"prods_r":[],"prods_h":[],"prods_p":[]},"Variedades":[],"Tams":[],"Estadios":[],"Logs":[]}
            utility.create_db(self.file,{"Espacios":[],"Productos":{"prods_r":[],"prods_h":[],"prods_p":[]},"Variedades":[],"Tams":[],"Estadios":[],"Logs":[]})
        else:
            cred = credentials.Certificate(os.path.dirname(__file__) + "\\depot.json")
            firebase_admin.initialize_app(cred,
                {
                'databaseURL': os.getenv("fb"),
                'databaseAuthVariableOverride': {'id': "laburante"}
                })
            
        self.update_db()

        self.edit_mode = -1
        self.act_mode = -1

        self.selected_p = []
        self.selected_subesp = None
        self.selected_esp  = None

        self.init_app()
        self.home_url = None
        self.fecha_esquejes = None 
    #TODO validate entry / diff users
    def login(self):
        if flask.request.method == 'POST':
            user = flask.request.form['user'] 
            passw = flask.request.form['passw']
            if user == "administrador" and passw == "administrador":
                flask.session["username"] = user
                return flask.redirect(flask.url_for("home"))
            else: flask.flash("Usuario/Contraseña equivocada","warning")

        return flask.render_template('index.html')

    def home(self):
        if self.home_url is None:
            self.home_url = flask.url_for("home")
        
        if "username" not in flask.session:
            return flask.redirect(flask.url_for('login'))

        if flask.request.method == "POST":
            self.selected_esp =  self.selected_subesp = None
            self.selected_p.clear()
            form = flask.request.form

            for planta in self.plants:
                a = form.get(f'{planta["ID"]}',default=None)
                if a is not None: self.selected_p.append(planta)

            #if edit/log pressed redirect edit/log for the selected subspace
            log = flask.request.form.get("log",-1)
            log_s = flask.request.form.get("log_s",-1)

            if log_s != -1:
                self.act_mode = 61
                id = utility.get_loc_idx(log_s) 
                self.selected_subesp = self.espacios[id[0]]["Subespacios"][id[1]]
                return flask.redirect(flask.url_for("actividad"))
            elif log != -1:
                self.act_mode = 62
                self.selected_esp = self.espacios[utility.get_loc_idx(log)[0]]
                return flask.redirect(flask.url_for("actividad"))
            
            #bitacora o actividad -> separar plantas seleccionadas -> ir al url segun actividad/bitacora
            modes = ["Riego","Pulverizacion","Tratamiento Plagas","Tratamiento Hongos","Poda","Transplante","Bitacora"]

            if len(self.selected_p) == 0:
                flask.flash("Porfavor seleccionar por lo menos una planta",category="warning")
                return flask.redirect(flask.url_for("home"))

            if flask.request.form.get("bit_p",-1) != -1:
                return flask.redirect(flask.url_for("show_log"))

            if form['mode'] in modes:
                self.act_mode = modes.index(form["mode"])
                return flask.redirect(flask.url_for("actividad"))
            if form["mode"] == "Modificar":
                self.edit_mode = 0
                return flask.redirect(flask.url_for("mod"))

        add_p = flask.url_for("add_p")
        config = flask.url_for("configuracion")
        hist_stock = flask.url_for("check_stock")
        hist_riego = flask.url_for("check_riegos")

        return flask.render_template("home.html",cant_plantas=len(self.plants)-self.clones_cant,clones = self.clones_cant,espacios=self.espacios,add_p=add_p,config=config,hist_stock=hist_stock,hist_riego=hist_riego,user=flask.session["username"])
#----------------------------------------------ACTIVIDADES----------------------------------------------------------------------------------------#
    #TODO log with user id 
    def actividad(self):
        
        if "username" not in flask.session:
            return flask.redirect(flask.url_for('login'))
        
        #riego = 0, pulve = 1, trat_p = 2, trat_h = 3,trans = 5, poda = 4, bitacora = 6
        if flask.request.method == "POST":
            form = flask.request.form 
            modo = int(form["modo"])

            plantas = form.getlist("planta")
            selected_p = []
            for planta in plantas:
                p_var = utility.get_var_id(planta)
                for var in self.variedades:
                    if var["Nombre"] == p_var[0]:
                        loc = utility.get_loc_idx(var["Individuos"][p_var[1]]["Loc"])
                        for indiv in self.espacios[loc[0]]["Subespacios"][loc[1]]["Individuos"]:
                            if indiv["ID"] == planta: selected_p.append(indiv)

            ids = [planta["ID"] for planta in selected_p]

            if modo <= 3:                
                self.riego_p_trat(modo,form,ids)
            elif modo == 5:
                self.transplant(form,selected_p)                       
            elif modo == 4:
                return self.poda(form,ids)
            elif modo >= 6:
                self.bitacora(modo,form,ids)

            return flask.redirect(flask.url_for("home"))

        prods = None
        if self.act_mode <= 1:prods = self.prods_riego
        elif  self.act_mode == 2:prods = self.prods_plagas
        elif self.act_mode == 3: prods = self.prods_hongos

        if self.act_mode < 61: return flask.render_template("actividad.html",productos = prods,plantas=self.selected_p,modo=self.act_mode,tams=self.tams)
     
        if self.act_mode == 61: return flask.render_template("actividad.html",sube = self.selected_subesp,modo=self.act_mode)
        
        if self.act_mode == 62: return flask.render_template("actividad.html",esp = self.selected_esp,modo=self.act_mode)

    def riego_p_trat(self,modo:int,form:dict,ids:list):
        prods_usados = []
        prods = form.getlist("producto")
        medidas = form.getlist("medida")
        for i in range(len(prods)): prods_usados.append([prods[i],medidas[i]])
        log = {"Fecha":form["fecha"],"IDs":ids,"Log":{"ID":modo,"Comment":form["comment"],
                                                                                   "Cantidad":form["cantidad"],"PH":form["ph"],
                                                                                   "EC":form["ec"],"Prods":prods_usados}}
        utility.add_log(self.file,[log]) if self.debug else utility.add_log_fbd(db,[log]) 
                
        pass
    
    def poda(self,form,ids:list):
        tipo_poda = form["metodo"]
        fecha = form["fecha"]
        comment = form["comment"]
        log = {"Fecha":fecha,"IDs":ids,"Log":{"ID":4,"Comment":comment,"Tipo":tipo_poda}}
        utility.add_log(self.file,[log]) if self.debug else utility.add_log_fbd(db,[log])
        
        if tipo_poda == "Poda de esquejes":
            self.fecha_esquejes = fecha
            return flask.redirect(flask.url_for("clone"))

    def clone(self):
        if "username" not in flask.session:
            return flask.redirect(flask.url_for('login'))

        if flask.request.method == "POST":
            clones = flask.request.form.getlist("clones")
            subes = flask.request.form.getlist("sube")
            tams = flask.request.form.getlist("tam")
            vars = flask.request.form.getlist("var")
            cambio_por_sube = {sube : [] for sube in subes}
            cambio_por_sube_yvar = {}

            for i in range(len(subes)):
                id_e = utility.get_loc_idx(subes[i])
                var = vars[i]
                for j in range(len(self.variedades)):
                    if self.variedades[j]["Nombre"] == var:
                        for _ in range(int(clones[i])):
                            clon_i = {"ID":None,"Estadio":"Clon","Tam":tams[i]}
                            id_n = len(self.variedades[j]["Individuos"])
                            clon_i["ID"] = var + "-" + str(id_n)
                            self.variedades[j]["Individuos"].append(clon_i)
                            self.espacios[id_e[0]]["Subespacios"][id_e[1]]["Individuos"].append(clon_i)
                            if subes[i] in cambio_por_sube_yvar.keys(): 
                                if j in cambio_por_sube_yvar[subes[i]].keys():cambio_por_sube_yvar[subes[i]][j].append(clon_i)
                                else:cambio_por_sube_yvar[subes[i]][j]= [clon_i]
                            else:  cambio_por_sube_yvar[subes[i]] = {j:[clon_i]}


                            cambio_por_sube[subes[i]].append(clon_i["ID"])
                            utility.add_plant(self.file,id_e[0],id_e[1],j,clon_i) if self.debug else None
                        break
            logs = []
            for sube in cambio_por_sube.keys(): 
                log = {"Fecha":self.fecha_esquejes,"IDs":cambio_por_sube[sube],"Log":{"ID":9,"Loc":sube}}
                logs.append(log)

            if not self.debug:
                for key in cambio_por_sube_yvar:
                    esp = utility.get_loc_idx(key)
                    for var in cambio_por_sube_yvar[key]: utility.add_planta_fdb(db,esp[0],esp[1],var,cambio_por_sube_yvar[key][var])

            self.update_db()

            if logs:
                if self.debug: utility.add_log(self.file,logs)
                else: utility.add_log_fbd(db,logs)

            return flask.redirect(flask.url_for("home"))
        
        vars = []
        for planta in self.selected_p: 
            if utility.get_var_id(planta["ID"]) not in vars: vars.append(utility.get_var_id(planta["ID"])[0])
    
        return flask.render_template("clone.html",vars=vars,fecha=self.fecha_esquejes,tams=self.tams,espacios=self.espacios)

    def transplant(self,form,plantas:list):
        fechas = form.getlist("fecha")
        tams = form.getlist("tam")
        fechag = form.get("fechaglob",-1)
        tamg = form.get("tamglob",-1)

        cambios_por_fecha = {}
        cambios_glob = []

        for i in range(len(plantas)):
            planta = plantas[i]
            if form.get(planta["ID"],-1) != -1: cambios_glob.append(planta)
            else:
                if fechas[i] in cambios_por_fecha.keys():
                    if tams[i] in cambios_por_fecha[fechas[i]].keys():
                        cambios_por_fecha[fechas[i]][tams[i]].append(planta)
                    else:
                        cambios_por_fecha[fechas[i]][tams[i]] = [planta]
                else:
                    cambios_por_fecha[fechas[i]] = {tams[i] : [planta]}

        logs = []
        if cambios_glob: 
           utility.mod_plant(self.file,cambios_glob,size=tamg) if self.debug else utility.mod_plant_fbd(db,cambios_glob,size=tamg)
           #TODO test
           clones = []
           for planta in plantas:
                p_var = utility.get_var_id(planta["ID"])
                loc_id = None
                for var in self.variedades:
                    if var["Nombre"] == p_var[0]: loc_id  = utility.get_loc_idx(var['Individuos'][p_var[1]]["Loc"])
                if self.espacios[loc_id[0]]["Subespacios"][loc_id[1]]["Clones"]: clones.append(planta)
                
           if len(clones) > 0: 
               log = {"Fecha":fechag,"IDs":[clon["ID"] for clon in clones],"Log":{"ID":10,"Est":self.ests[0]}}
               logs.append(log)
               utility.mod_plant(self.file,clones,estadio=self.ests[0]) if self.debug else utility.mod_plant_fbd(db,clones,estadio=self.ests[0])

           log = {"Fecha":fechag,"IDs":[planta["ID"] for planta in plantas],"Log":{"ID":5,"Tam":tamg}}
           logs.append(log)
 

        for fecha in cambios_por_fecha.keys():
            for tam in cambios_por_fecha[fecha].keys():
                utility.mod_plant(self.file,plantas,size=tam) if self.debug else utility.mod_plant_fbd(db,plantas,size=tam)
                clones = []
                for planta in plantas:
                    p_var = utility.get_var_id(planta["ID"])
                    loc_id = None
                    for var in self.variedades:
                        if var["Nombre"] == p_var[0]: loc_id  = utility.get_loc_idx(var['Individuos'][p_var[1]]["Loc"])
                    if self.espacios[loc_id[0]]["Subespacios"][loc_id[1]]["Clones"]: clones.append(planta)
                        
                
                if len(clones) > 0:
                    log = {"Fecha":fecha,"IDs":[clon["ID"] for clon in clones],"Log":{"ID":10,"Est":self.ests[0]}}
                    logs.append(log)
                    utility.mod_plant(self.file,clones,estadio=self.ests[0]) if self.debug else utility.mod_plant_fbd(db,clones,estadio=self.ests[0])
                log = {"Fecha":fecha,"IDs":[planta["ID"] for planta in plantas],"Log":{"ID":5,"Tam":tam}}
                logs.append(log)

        if logs:
            if self.debug: utility.add_log(self.file,logs)
            else: utility.add_log_fbd(db,logs)

        self.update_db()

    def bitacora(self,modo,form,ids):
        fecha = form["fecha"]
        comment = form["comment"]

        if modo == 61:ids = [form["sube"]]
        elif modo == 62: ids = [form["esp"]]
        log = {"Fecha":fecha,"IDs":ids,"Log":{"ID":modo,"Comment":comment}}
        utility.add_log(self.file,[log]) if self.debug else utility.add_log_fbd(db,[log])
#----------------------------------------------ADD-----------------------------------------------------------------------------------------------#
    def add_p(self): 
        if "username" not in flask.session:
            return flask.redirect(flask.url_for('login'))

        if flask.request.method == "POST":
            var = flask.request.form.getlist('variedad')
            subes = flask.request.form.getlist('sube')
            fechas = flask.request.form.getlist('fecha')
            tams = flask.request.form.getlist('tam')
            ests = flask.request.form.getlist('est')
            finals_ids = []
            fechas_logs = {}
            
            final_plants = {}

            for i in range(len(var)):
                plant = {"ID":None,"Estadio":ests[i],"Tam":tams[i]}
                id = utility.get_loc_idx(subes[i])

                for j in range(len(self.variedades)):
                    if self.variedades[j]["Nombre"] == var[i]:
                        id_n = len(self.variedades[j]['Individuos'])
                        plant["ID"] = var[i] + "-" + str(id_n)
                        self.variedades[j]["Individuos"].append(plant)
                        finals_ids.append(plant["ID"])
                        
                        self.espacios[id[0]]["Subespacios"][id[1]]["Individuos"].append(plant)

                        if subes[i] in final_plants.keys(): 
                            if j in final_plants[subes[i]].keys():final_plants[subes[i]][j].append(plant)
                            else:final_plants[subes[i]][j] = [plant]
                        else:  final_plants[subes[i]] =  {j : [plant]}

                        utility.add_plant(self.file,id[0],id[1],j,plant) if self.debug else None
                        break
            
                if f"{fechas[i]}" in fechas_logs.keys():
                    if subes[i] in fechas_logs[f"{fechas[i]}"].keys():fechas_logs[f"{fechas[i]}"][subes[i]].append(finals_ids[-1])
                    else:fechas_logs[f"{fechas[i]}"][subes[i]] = [finals_ids[-1]]
                else:fechas_logs[f"{fechas[i]}"] = {subes[i] : [finals_ids[-1]]}
                
            if not self.debug:
                for key in final_plants:
                    esp = utility.get_loc_idx(key)
                    for var in final_plants[key]: utility.add_planta_fdb(db,esp[0],esp[1],var,final_plants[key][var])
            
            logs = []
            for fecha in fechas_logs.keys():
                for sube in fechas_logs[fecha].keys():logs.append({"Fecha":fecha,"IDs":fechas_logs[fecha][sube],"Log":{"ID":9,"Loc":sube}})

            utility.add_log(self.file,logs) if self.debug else utility.add_log_fbd(db,logs)
            
            #self.update_db()
            return flask.redirect(flask.url_for("home"))

        return flask.render_template("add_p.html",espacios=self.espacios,variedades=self.variedades,tams=self.tams,ests=self.ests)
#---------------------------------------------MOD-----------------------------------------------------------------------------------------------#
    def mod(self):
        if "username" not in flask.session:
            return flask.redirect(flask.url_for('login'))
        
        #0 = plantas, 1 = espacio
        if flask.request.method == "POST":
            form = flask.request.form
            modo = int(form["modo"])
            
            if modo ==  0:            

                plantas = form.getlist("planta")
                selected_p = []
                for planta in plantas:
                    p_var = utility.get_var_id(planta)
                    for var in self.variedades:
                        if var["Nombre"] == p_var[0]:
                            loc = utility.get_loc_idx(var["Individuos"][p_var[1]]["Loc"])
                            for indiv in self.espacios[loc[0]]["Subespacios"][loc[1]]["Individuos"]:
                                if indiv["ID"] == planta: selected_p.append(indiv)

                fechas = form.getlist("fecha")
                sube = form.getlist("sube")
                est =  form.getlist("Estadio") 
                
                fechag = form.get("fechag",-1)
                subg = form.get("subeglob",-1)
                estg = form.get("Estadioglob",-1)
                self.mod_plants(form,selected_p,fechas,est,sube,fechag,subg,estg)

                self.update_db()
            
            if modo == 1:
                sel_esp = self.espacios[utility.get_loc_idx(form.get("esp",-1))[0]]
                delete = form.get("delete",-1)
                del_sube = form.get("del_sube",-1)
                self.mod_esp(form,sel_esp,delete,del_sube)
            
            
            return flask.redirect(flask.url_for("home"))

        if self.edit_mode == 0:
            return flask.render_template("modificar.html",espacios=self.espacios,mode=self.edit_mode,plantas=self.selected_p,ests=self.ests)
        
        elif self.edit_mode == 1:
            
            plantas = d_plantas = 0
            if "Subespacios" not in self.selected_esp.keys():
                subes = []
            else: subes = self.selected_esp["Subespacios"]


            for sube in subes:
                for planta in sube["Individuos"]:
                    if planta["Estadio"] == "Muerta": d_plantas+=1
                    plantas += 1
            vacio = True if plantas == d_plantas else False

            return flask.render_template("modificar.html",vacio=vacio,mode=self.edit_mode,espacio=self.selected_esp)
    #TODO mod locally and try to organice better the code
    def mod_plants(self,form,selected_p,fechas,est,sube,fechag,subg,estg):
        glob_p = []
        cambios_por_fecha = {}
        for i in range(len(selected_p)):
            planta = selected_p[i]
            if form.get(planta["ID"],-1) != -1:glob_p.append(planta)
            else: 
                if sube[i] != "Seleccionar":
                    if f"{fechas[i]}" in cambios_por_fecha.keys():
                        if f"{sube[i]}" in cambios_por_fecha[f"{fechas[i]}"][0].keys():
                            cambios_por_fecha[f"{fechas[i]}"][0][f"{sube[i]}"].append(planta)
                        else:
                            cambios_por_fecha[f"{fechas[i]}"][0][f"{sube[i]}"] = [planta]
                    else: 
                        cambios_por_fecha[f"{fechas[i]}"] = [{},{}]
                        cambios_por_fecha[f"{fechas[i]}"][0][f"{sube[i]}"] = [planta]
                
                if est[i] != "Seleccionar":
                    if f"{fechas[i]}" in cambios_por_fecha.keys():
                        if f"{est[i]}" in cambios_por_fecha[f"{fechas[i]}"][1].keys():
                            cambios_por_fecha[f"{fechas[i]}"][1][f"{est[i]}"].append(planta)
                        else:
                            cambios_por_fecha[f"{fechas[i]}"][1][f"{est[i]}"] = [planta]
                    else: 
                        cambios_por_fecha[f"{fechas[i]}"] = [{},{}]
                        cambios_por_fecha[f"{fechas[i]}"][1][f"{est[i]}"] = [planta]
        
        logs = []
        if subg != "Seleccionar" or estg != "Seleccionar":
            glob_ids = [planta["ID"] for planta in glob_p]
            if subg != "Seleccionar" and estg != "Seleccionar":
                log = {"Fecha":fechag,"IDs":glob_ids,"Log":{"ID":7,"Loc":subg}},{"Fecha":fechag,"IDs":glob_ids,"Log":{"ID":10,"Est":estg}} 
                if self.debug:
                    utility.mod_plant(self.file,glob_p,subg,estg)
                    logs.append(log)                        
                else:
                    utility.mod_plant_fbd(db,glob_p,subg,estg)
                    logs.append(log)
            elif subg != "Seleccionar":
                log = {"Fecha":fechag,"IDs":glob_ids,"Log":{"ID":7,"Loc":subg}}
                if self.debug:
                    utility.mod_plant(self.file,glob_p,subg)
                    logs.append(log)
                else:
                    utility.mod_plant_fbd(db,glob_p,subg)
                    logs.append(log)
            elif estg != "Seleccionar":
                if self.debug:
                    utility.mod_plant(self.file,glob_p,estadio=estg) 
                    if estg == "Muerta":logs.append({"Fecha":fechag,"IDs":glob_ids,"Log":{"ID":8}})
                    else: logs.append({"Fecha":fechag,"IDs":glob_ids,"Log":{"ID":10,"Est":estg}})
                else:
                    utility.mod_plant_fbd(db,glob_p,estadio=estg) 
                    if estg == "Muerta":logs.append({"Fecha":fechag,"IDs":glob_ids,"Log":{"ID":8}})
                    else: logs.append({"Fecha":fechag,"IDs":glob_ids,"Log":{"ID":10,"Est":estg}})

        for fecha in cambios_por_fecha.keys():
            for sube in cambios_por_fecha[fecha][0].keys():
                ids = [planta["ID"] for planta in cambios_por_fecha[fecha][0][sube]]
                if self.debug:
                    utility.mod_plant(self.file,cambios_por_fecha[fecha][0][sube],sube=sube)
                    logs.append({"Fecha":fecha,"IDs":ids,"Log":{"ID":7,"Loc":sube}})
                else:
                    utility.mod_plant_fbd(db,cambios_por_fecha[fecha][0][sube],sube=sube)
                    logs.append({"Fecha":fecha,"IDs":ids,"Log":{"ID":7,"Loc":sube}})
                    
            for est in cambios_por_fecha[fecha][1].keys():
                ids = [planta["ID"] for planta in cambios_por_fecha[fecha][1][est]]
                if self.debug:
                    utility.mod_plant(self.file,cambios_por_fecha[fecha][1][est],estadio=est)
                    if est != "Muerta":logs.append({"Fecha":fecha,"IDs":ids,"Log":{"ID":10,"Est":est}})
                    else: logs.append({"Fecha":fecha,"IDs":ids,"Log":{"ID":8,"Est":est}})
                else:
                    utility.mod_plant_fbd(db,cambios_por_fecha[fecha][1][est],estadio=est)
                    if est != "Muerta":logs.append({"Fecha":fecha,"IDs":ids,"Log":{"ID":10,"Est":est}})
                    else: logs.append({"Fecha":fecha,"IDs":ids,"Log":{"ID":8,"Est":est}})

        if logs:
            if self.debug : utility.add_log(self.file,logs)
            else: utility.add_log_fbd(db,logs)

    def mod_esp(self,form,sel_esp,delete,del_sube):
        if delete != -1: 
            id = utility.get_loc_idx(delete)
            self.espacios[id[0]]["Existe"] = False
            utility.delete(self.file,"Espacios",id[0]) if self.debug else utility.delete_fdb(db,"Espacios",id[0])
        elif del_sube != -1: 
            id = utility.get_loc_idx(del_sube)
            self.espacios[id[0]]["Subespacios"][id[1]]["Existe"] = False
            utility.delete(self.file,"Espacios",id[0],"Subespacios",id[1]) if self.debug else utility.delete_fdb(db,"Espacios",id[0],"Subespacios",id[1])
            self.selected_esp = sel_esp
            self.edit_mode = 1
            return flask.redirect(flask.url_for("mod"))
        else:
            esp_id = utility.get_loc_idx(form.get("esp",-1))[0]
            subesp = form.getlist("nombre")
            subes = []
            for sube in subesp:
                if len(sube) == 0: continue
                new_id = sel_esp["ID"] + "S-" + f"{len(self.espacios[esp_id]['Subespacios'])}"
                s = {'ID':new_id,'Nombre':sube,"Clones":False,'Individuos':[],"Existe":True}
                self.espacios[esp_id]["Subespacios"].append(s)  
                subes.append(s)

            utility.add_sube(self.file,esp_id,subes) if self.debug else utility.add_sube_fdb(db,esp_id,subes)
#-------------------------------------------LOGS---------------------------------------------------------------------------------------------------#
    def show_log(self):
        if "username" not in flask.session:
            return flask.redirect(flask.url_for('login'))
        
        self.update_db()
        plantas = self.selected_p
        ids = [planta["ID"] for planta in plantas]
        
        if self.debug: logs = self.db["Logs"] 
        else:
            log_ref = db.reference("/Logs").get()
            logs = []
            for entry in log_ref:
                for log in log_ref[entry]:logs.append(log)
        
        
        logs.sort(key=lambda log: log["Fecha"])
        trans = {}
        for esp in self.espacios:
            trans[esp["ID"]] = esp["Nombre"]
            for sube in esp["Subespacios"]: trans[sube["ID"]] = esp["Nombre"] + "-" + sube["Nombre"] 
        curr_state = [None for _ in range(len(plantas))]
        final_logs = {}

        for log in logs:
            #7 = movida  / 9 = aparece 
            if log["Log"]["ID"] in [7,9]:
                intersect = list(filter(lambda x:x in log["IDs"],ids))
                for i in range(len(plantas)):  curr_state[i] = log["Log"]["Loc"] if plantas[i]["ID"] in log["IDs"] else curr_state[i]

                if len(intersect) > 0:
                    if log["Fecha"] in final_logs.keys():final_logs[log["Fecha"]].append([intersect,log])
                    else:final_logs[log["Fecha"]] = [[intersect,log]]
                
                continue


            #61 = log sube / 62 = log esp
            if log["Log"]["ID"] in [61,62]:
                pos = -1
                loc_id_log = utility.get_loc_idx(log["IDs"][0])
                for i in range(len(plantas)):
                    if curr_state[i] is None: continue

                    loc_id_p = utility.get_loc_idx(curr_state[i])
                    
                    if loc_id_p[0] == loc_id_log[0] or loc_id_p == loc_id_log: #Mismo sube o mismo espacios
                        if log["Fecha"] in final_logs.keys():
                            if pos == -1:
                                final_logs[log["Fecha"]].append([[plantas[i]["ID"]],log])
                                pos = len(final_logs[log["Fecha"]]) - 1
                            else: final_logs[log["Fecha"]][pos][0].append(plantas[i]["ID"])
                        else:
                            final_logs[log["Fecha"]] = [[[plantas[i]["ID"]],log]]
                            pos = 0
                    
                continue

            
            
            intersect = list(filter(lambda x:x in log["IDs"],ids))
            if len(intersect) > 0:
                if log["Fecha"] in final_logs.keys(): final_logs[log["Fecha"]].append([intersect,log])
                else: final_logs[log["Fecha"]] = [[intersect,log]]


        return flask.render_template("bitacora.html",logs=final_logs,plantas=plantas,trans=trans)

    def check_riegos(self):
        if "username" not in flask.session:
            return flask.redirect(flask.url_for('login'))

        act_month = datetime.date.today().month
        if self.debug: all_logs = self.db["Logs"]
        else:
            log_ref = db.reference("/Logs").get()
            all_logs = []
            for entry in log_ref:
                for log in log_ref[entry]:all_logs.append(log)
        
        logs = []
        for log in all_logs:
            if (log["Log"]["ID"] in [0,1] ):
                month = log["Fecha"][5:7]
                if month[0] == "0":
                    month = month[1]
                if int(month) == act_month:
                    logs.append(log)
        logs.sort(key=lambda log: log["Fecha"])


        fechas = {log["Fecha"] : [] for log in logs}
        for log in logs:fechas[log["Fecha"]].append(log)

        if logs: return flask.render_template("check.html",logs=fechas,modo=1)
        else:
            flask.flash("No hay logs para mostrar")
            return flask.redirect(flask.url_for("home"))

    def check_stock(self):
        if "username" not in flask.session:
            return flask.redirect(flask.url_for('login'))

        act_month = datetime.date.today().month
        logs = []
        last_count = {}
        ult_stock_count = 0
        translate = {}
        for esp in self.espacios:
            translate[esp["ID"]] = esp["Nombre"]
            last_count[esp["ID"]] = 0
            for sube in esp["Subespacios"]:
                last_count[sube["ID"]] = 0
                translate[sube["ID"]] = esp["Nombre"] + "-" + sube["Nombre"]

        if self.debug: all_logs = self.db["Logs"]
        else:
            log_ref = db.reference("/Logs").get()
            all_logs = []
            for entry in log_ref:
                for log in log_ref[entry]:all_logs.append(log)


        for log in all_logs:
            if (log["Log"]["ID"] in [8,9] ):
                month = log["Fecha"][5:7]
                if month[0] == "0":
                    month = month[1]


                if int(month) == act_month:
                    logs.append(log)

                elif int(month) < act_month:
                    if log["Log"]["ID"] == 9: 
                        last_count[log["Log"]["Loc"][0]] += len(log["IDs"])
                        ult_stock_count+=len(log["IDs"])
                    else: 
                        last_count[log["Log"]["Loc"][0]]-= len(log["IDs"])
                        ult_stock_count-=len(log["IDs"])

        logs.sort(key=lambda log: log["Fecha"])

        fechas = {log["Fecha"] : [{},[]] for log in logs}
        mm = last_count.copy()

        for log in logs:
            a = len(log["IDs"]) if log["Log"]["ID"] == 9 else -len(log["IDs"])
            
            if log["Log"]["Loc"] not in fechas[log["Fecha"]][0].keys(): fechas[log["Fecha"]][0][log["Log"]["Loc"]] = mm[log["Log"]["Loc"]] + a
            else: fechas[log["Fecha"]][0][log["Log"]["Loc"]] += a
            
            fechas[log["Fecha"]][1].append(log)    
            
            mm[log["Log"]["Loc"]] += a 


        if logs: return flask.render_template("check.html",logs=fechas,modo=0,ult_stock_g=last_count,trans=translate,ult_stock=ult_stock_count)
        else:
            flask.flash("No hay logs para mostrar")
            return flask.redirect(flask.url_for("home"))
#------------------------------------------CONFIGURACION-------------------------------------------------------------------------------------------#
    def configuracion(self):
        if "username" not in flask.session:
            return flask.redirect(flask.url_for('login'))

        if flask.request.method == "POST":
            form = flask.request.form
            
            #Redirect
            if form.get("espb",-1) != -1:
                return flask.render_template("cnf.html",modo=1,home=self.home_url,espacios=self.espacios)
            if form.get("varb",-1) != -1:
                return flask.render_template("cnf.html",modo=2,home=self.home_url,variedades=self.variedades)
            if form.get("prodb",-1) != -1:
                return flask.render_template("cnf.html",modo=3,home=self.home_url,prods_r=self.prods_riego,prods_p=self.prods_plagas,prods_h=self.prods_hongos)
            if form.get("tamb",-1) != -1:
                return flask.render_template("cnf.html",modo=4,home=self.home_url,tams=self.tams)
            if form.get("estb",-1) != -1:
                return flask.render_template("cnf.html",modo=5,home=self.home_url,ests=self.ests)
            if form.get("cloneb",-1) != -1:
                return flask.render_template("cnf.html",modo=6,espacios=self.espacios)
            if form.get("edit",-1) != -1:
                esp = form["edit"]
                self.selected_esp = self.espacios[utility.get_loc_idx(esp)[0]]
                self.edit_mode = 1
                return flask.redirect(flask.url_for('mod'))


            #Deletion
            if form.get("delVar",-1) != -1:
                var_to_del = form.get("delVar",-1)
                for i in range(len(self.variedades)):
                    var = self.variedades[i]["Nombre"]
                    if var == var_to_del:
                        self.variedades.pop(i)
                        utility.delete(self.file,"Variedades",i) if self.debug else utility.delete_fdb(db,"Variedades",i)
                        break

                return flask.render_template("cnf.html",modo=2,home=self.home_url,variedades=self.variedades)

            if form.get("delPR",-1) != -1:
                prod_to_del = form.get("delPR",-1)
                for i in range(len(self.prods_riego)):
                    if self.prods_riego[i] == prod_to_del:
                        self.prods_riego.pop(i)
                        utility.delete(self.file,"Productos",type2="prods_r",idx2=i) if self.debug else utility.delete_fdb(db,"Productos",type2="prods_r",idx2=i)
                        break

                return flask.render_template("cnf.html",modo=3,home=self.home_url,prods_r=self.prods_riego,prods_p=self.prods_plagas,prods_h=self.prods_hongos)
            
            if form.get("delPP",-1) != -1:
                prod_to_del = form.get("delPR",-1)
                for i in range(len(self.prods_plagas)):
                    if self.prods_plagas[i] == prod_to_del:
                        self.prods_plagas.pop(i)
                        utility.delete(self.file,"Productos",type2="prods_p",idx2=i) if self.debug else utility.delete_fdb(db,"Productos",type2="prods_p",idx2=i)
                        break

                return flask.render_template("cnf.html",modo=3,home=self.home_url,prods_r=self.prods_riego,prods_p=self.prods_plagas,prods_h=self.prods_hongos)
            
            if form.get("delPH",-1) != -1:
                prod_to_del = form.get("delPH",-1)
                for i in range(len(self.prods_hongos)):
                    if self.prods_hongos[i] == prod_to_del:
                        self.prods_hongos.pop(i)
                        utility.delete(self.file,"Productos",type2="prods_h",idx2=i) if self.debug else utility.delete_fdb(db,"Productos",type2="prods_h",idx2=i)
                        break

                return flask.render_template("cnf.html",modo=3,home=self.home_url,prods_r=self.prods_riego,prods_p=self.prods_plagas,prods_h=self.prods_hongos)

            if form.get("delT",-1) != -1:
                tam_to_del = form.get("delT",-1)
                for i in range(len(self.tams)):
                    if self.tams[i] == tam_to_del:
                        self.tams.pop(i)
                        utility.delete(self.file,"Tams",i) if self.debug else utility.delete_fdb(db,"Tams",i)
                        break
                
                return flask.render_template("cnf.html",modo=4,home=self.home_url,tams=self.tams) 
        
            if form.get("delE",-1) != -1:
                est_to_del = form.get("delE",-1)
                for i in range(len(self.ests)):
                    if self.ests[i] == est_to_del:
                        self.ests.pop(i)
                        utility.delete(self.file,"Estadios",i) if self.debug else utility.delete_fdb(db,"Estadios",i)
                        break
                
                return flask.render_template("cnf.html",modo=5,home=self.home_url,ests=self.ests) 

            #Edits
            es_names = form.getlist("nombre")
            v_names = form.getlist("nombre_v")
            p_names = form.getlist("nombre_p")
            tipos = form.getlist("tipo")
            tams = form.getlist("tam")
            ests = form.getlist("est")

            if len(es_names) > 0:
                espacios = []
                for name in es_names:
                    id = "E-" + str(len(self.espacios))
                    espacio = {"ID":id,"Nombre":name,"Subespacios":[],"Existe":True}
                    espacios.append(espacio)
                    self.espacios.append(espacio)

                utility.add_to_db(self.file,espacios) if self.debug else utility.add_to_fdb(db,espacios)

            if len(v_names) > 0:
                nvs = []
                for v in v_names:
                    nv = {"Nombre":v,"Individuos":[]}
                    self.variedades.append(nv)
                    nvs.append(nv)

                utility.add_to_db(self.file,variedades=nvs) if self.debug else utility.add_to_fdb(db,variedades=nvs)

            if len(p_names) > 0:
                prods = []
                for i in range(len(p_names)):
                    tipo_fin = None
                    if tipos[i] == "Riego/Pulverizacion": 
                        self.prods_riego.append(p_names[i])
                        tipo_fin = "prods_r"
                    elif tipos[i] == "Tratamiento Plagas": 
                        self.prods_plagas.append(p_names[i])
                        tipo_fin = "prods_p"
                    else: 
                        self.prods_hongos.append(p_names[i])
                        tipo_fin = "prods_h"
                    
                    prods.append([p_names[i],tipo_fin])

                utility.add_to_db(self.file,prods=prods) if self.debug else utility.add_to_fdb(db,prods=prods)

            if len(tams) > 0:
                for i in range(len(tams)):
                    self.tams.append(tams[i])

                utility.add_to_db(self.file,tams=tams) if self.debug else utility.add_to_fdb(db,tams=tams) 
            
            if len(ests) > 0:
                for est in ests:
                    self.ests.append(est)

                utility.add_to_db(self.file,ests=ests) if self.debug else utility.add_to_fdb(db,ests=ests)
            
            if form.get("modo",-1) != -1: 
                for esp in self.espacios:
                    for sube in esp["Subespacios"]:
                        cl = True if form.get(sube["ID"],-1) != -1 else False                                        
                        id = utility.get_loc_idx(sube["ID"])
                        self.espacios[id[0]]["Subespacios"][id[1]]["Clones"] = cl
                        utility.mod_sube(self.file,id[0],id[1],cl) if self.debug else utility.mod_sube_fdb(db,id[0],id[1],cl)

            return flask.redirect(flask.url_for("configuracion"))

        return flask.render_template("cnf.html",modo=0,home=self.home_url)

    def init_app(self):
        self.app.add_url_rule("/",view_func=self.login,methods=["GET","POST"])
        self.app.add_url_rule("/home",view_func=self.home,methods=["GET","POST"])
        self.app.add_url_rule("/bitacora",view_func=self.show_log,methods=["GET","POST"])
        self.app.add_url_rule("/añadir planta",view_func=self.add_p,methods=["GET","POST"])
        self.app.add_url_rule("/actividad",view_func=self.actividad,methods=["GET","POST"])
        self.app.add_url_rule("/modificar",view_func=self.mod,methods=["GET","POST"])
        self.app.add_url_rule("/ultimos riegos",view_func=self.check_riegos,methods=["GET","POST"])
        self.app.add_url_rule("/cambios stock",view_func=self.check_stock,methods=["GET","POST"]) 
        self.app.add_url_rule("/configuracion",view_func=self.configuracion,methods=["GET","POST"])
        self.app.add_url_rule("/clonar",view_func=self.clone,methods=["GET","POST"])

    def update_db(self):
        self.db = utility.read_json(self.file) if self.debug else None

        self.plants = []
        self.clones_cant = 0

        if self.debug: self.espacios = self.db["Espacios"] 
        else:
            esp_ref = db.reference("/Espacios").get()
            self.espacios = [] if esp_ref is None else esp_ref

        for i in range(len(self.espacios)):
            espacio = self.espacios[i]
            if "Subespacios" not in espacio.keys():
                self.espacios[i]["Subespacios"] = []
                espacio["Subespacios"] = []
            for j in range(len(espacio["Subespacios"])): 
                sube = espacio["Subespacios"][j]
                if "Individuos" not in sube.keys():
                    self.espacios[i]["Subespacios"][j]["Individuos"] = []
                    sube["Individuos"] = []
                for ind in sube["Individuos"]:
                    if ind["Estadio"] != "Muerta" :
                        if sube["Clones"]: self.clones_cant+=1
                        self.plants.append(ind)    
        
        if self.debug:
            self.variedades = self.db["Variedades"] 
            self.prods_riego = self.db["Productos"]["prods_r"] 
            self.prods_plagas = self.db["Productos"]["prods_p"]
            self.prods_hongos = self.db["Productos"]["prods_h"]
            self.tams = self.db["Tams"] 
            self.ests = self.db["Estadios"] 
        else:
            self.variedades = db.reference("/Variedades").get() 
            self.prods_riego = db.reference("/Productos/prods_r").get()
            self.prods_hongos = db.reference("/Productos/prods_h").get()
            self.prods_plagas = db.reference("/Productos/prods_p").get()
            self.tams = db.reference("/Tams").get()
            self.ests = db.reference("/Estadios").get()

            if self.variedades is None:self.variedades = []
            for i in range(len(self.variedades)):
                if "Individuos" not in self.variedades[i].keys(): self.variedades[i]["Individuos"] = []
            if self.prods_riego is None:self.prods_riego = []
            if self.prods_plagas is None:self.prods_plagas= []
            if self.prods_hongos is None:self.prods_hongos = []
            if self.tams is None:self.tams = []
            if self.ests is None:self.ests = []

    def run(self):
        self.app.run(debug=True)
 
depo = Depo(False)
depo.run()