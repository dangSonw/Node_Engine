"""Nominal collection nodes use builtin port contracts and stable variable identities."""
from dataclasses import replace
from copy import deepcopy
from .registry import NodeSpec,Port


def is_user_collection(type_name):
    return isinstance(type_name,str) and any(type_name.startswith(kind+'<'+prefix)
        and type_name.endswith('>') for kind in ('array','map','set') for prefix in ('struct:','enum:'))


def collection_specs(schema,builtin):
    templates={
        'array':dict(zip(range(8,21),[3220,3230,3240,3250,3260,3270,3280,3290,3300,3310,3320,3700,3710])),
        'map':dict(zip(range(8,17),[3420,3430,3440,3450,3460,3470,3480,3490,3500])),
        'set':dict(zip(range(8,14),[3620,3630,3640,3650,3660,3670]))}
    for kind,tid in [('array',2300),('map',2360),('set',2350)]: templates[kind][24]=tid
    templates['array'].update({25:3720,26:3730,27:3740})
    for kind,tid in [('array',2110),('map',2120),('set',2130)]: templates[kind][28]=tid
    definitions=[('struct:'+n,d) for n,d in schema.structs.items()]+[('enum:'+n,d) for n,d in schema.enums.items()]
    for index,(element,definition) in enumerate(definitions):
        name=definition['name']; variable_id=definition.get('variable_id',800000+index*16)
        # Negative IDs cannot overlap builtin, component or function IDs.
        base=-(variable_id*128+1)
        for group,kind in enumerate(('array','map','set')):
            type_name=f'{kind}<{element}>'; prefix=base-group*32
            for scope_index,scope in enumerate(('','global','scene','entity')):
                label=(scope.title()+' ' if scope else '')+name+' '+kind.title()
                owner=(Port('Entity','entity','player'),) if scope=='entity' else ()
                args=owner+(Port('Name','string',name.lower()+'_'+kind),)
                options=dict(context=True,variable_type=type_name,variable_scope=scope,user_type=element,collection_type=type_name)
                yield NodeSpec(prefix-scope_index*2,f'Get {label} Variable',3,'pure',args,
                    (Port('Value',type_name),),function='GetUserVariable',variable_access='get',**options)
                yield NodeSpec(prefix-scope_index*2-1,f'Set {label} Variable',3,'action',
                    (Port('In','exec'),)+args+(Port('Value',type_name,{} if kind=='map' else []),),
                    (Port('Out','exec'),),function='SetUserVariable',variable_access='set',**options)
            def port(p):
                converted=p.type.replace('float',element)
                default=schema.default_value(converted) if p.default is not None and p.type=='float' else deepcopy(p.default)
                return replace(p,type=converted,default=default)
            for slot,tid in templates[kind].items():
                spec=builtin[tid]
                yield replace(spec,id=prefix-slot,name=spec.name.replace('Float',name),
                    inputs=tuple(port(p) for p in spec.inputs),outputs=tuple(port(p) for p in spec.outputs),
                    user_type=element,collection_type=type_name,collection_operation=spec.function.split('<')[0])
