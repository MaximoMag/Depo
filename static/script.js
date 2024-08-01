
function copiar_div(div_to_copy,but)
{

    remove_x_but(div_to_copy)
    let div_copia = div_to_copy.cloneNode(true)
    let id_idx = div_to_copy.id.indexOf('_')
    let base_id = div_to_copy.id.substring(0,id_idx)
    let new_id_n = new Number(div_to_copy.id.substring(id_idx+1,div_to_copy.id.length))+1
    div_copia.id = `${base_id}_${new_id_n}`
    div_copia.name = div_copia.id
    
    let del_but = document.createElement('button')
    del_but.textContent = "X"
    del_but.type = "button"
    del_but.onclick = function(){remove_entry(del_but,div_copia,div_to_copy,base_id,new_id_n)}
    
    div_copia.insertAdjacentElement('beforeend',del_but)

    but.insertAdjacentElement('beforebegin',div_copia)
    but.onclick = function(){copiar_div(div_copia,but)}

}

function remove_entry(del_but,div_c,div_tc,id_base,idn)
{
    div_c.remove()
    del_but.remove()
    if (idn != 1)
    {
        div_tc.insertAdjacentElement('beforeend',del_but)
        last_id = `${id_base}_${idn-2}`
        last_div = document.getElementById(last_id)
        del_but.onclick = function(){remove_entry(del_but,div_tc,last_div,id_base,idn-1)}
    }
}


function remove_x_but(div)
{   
    let id = div.children.length-1
    if (div.children[id].type == 'button')
        div.children[id].remove()
}


function checkOtherBoxes(check,children){
    let v = check.checked;
    
    for(let a = 0;a<children.length;a++){
        if (children[a].type == "checkbox"){
            children[a].checked = check.checked;
        }else if(children[a].children.length > 0){
            checkOtherBoxes(check,children[a].children)
        }
    }
}


function hide_children(div)
{   
    let children = div.children
    for(let i = 0;i<children.length;i++) {hide_(children[i])};
}


function hide_(entry)
{
    let children = entry.children
    if (children != undefined) {for(let i = 0;i<children.length;i++) {hide_children(children[i])}}

    if(entry.style.display == "none") {entry.style.display = "block"}
    else {entry.style.display = "none"}
}