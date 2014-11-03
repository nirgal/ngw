import sys

# __hooks_group_hierarchy_changed__ = []
# def on_group_hierarchy_changed(func):
#     " decodator for extension functions that wants to be notified of group/subgroups hierarchy changes "
#     __hooks_group_hierarchy_changed__.append(func)
#     return func
# 
# def group_hierarchy_changed(request):
#     " Event dispatcher for group/subgroups hierarchy changes notifications "
#     print("CALLED group_hierarchy_changed", file=sys.stderr)
#     for f in __hooks_group_hierarchy_changed__:
#         f(request)

################
# Field changed
################

__hooks_contact_field_changed__ = {}
def add_hook_contact_field_changed(field_id, func):
    field_hooks = __hooks_contact_field_changed__.get(field_id, [])
    __hooks_contact_field_changed__[field_id] = field_hooks + [func]
    
def on_contact_field_changed(field_id):
    " decorator for extension functions that wants to be notified of a specific field changes"
    def wrapped(func):
        add_hook_contact_field_changed(field_id, func)
        return func
    return wrapped
 
def contact_field_changed(request, field_id, contact):
    " Event dispatcher for field change notifications"
    print("Dispatching notification contact_field_changed", field_id, contact, file=sys.stderr)
    for f in __hooks_contact_field_changed__.get(field_id, []):
        f(request, contact)

#####################
# Membership changed
#####################

__hooks_membership_changed__ = {}
def add_hook_membership_changed(group_id, func):
    membership_hooks = __hooks_membership_changed__.get(group_id, [])
    __hooks_membership_changed__[group_id] = membership_hooks + [func]

def on_membership_changed(group_id):
    " decorator for extension functions that wants to be notified of a specific group membership change"
    def wrapped(func):
        add_hook_membership_changed(group_id, func)
        return func
    return wrapped

def membership_changed(request, contact, group):
    "Event dispatcher for membership change notification"
    print("Dispatching notification membership_changed", contact, group, file=sys.stderr)
    for sg in group.get_self_and_supergroups():
        print("Dispatching notification membership_changed", contact, group, ": supergroup", sg, file=sys.stderr)
        for f in __hooks_membership_changed__.get(sg.id, []):
            f(request, contact, sg)
    
