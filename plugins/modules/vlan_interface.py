#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2022, Felix Fontein <felix@fontein.de>
# GNU General Public License v3.0+ https://www.gnu.org/licenses/gpl-3.0.txt
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.text.converters import to_native

from ansible_collections.community.routeros.plugins.module_utils.api import (
    api_argument_spec,
    check_has_library,
    create_api,
)

from ansible_collections.community.routeros.plugins.module_utils._api_data import (
    split_path,
)

try:
    from librouteros.exceptions import LibRouterosError
except Exception:
    # Handled in api module_utils
    pass


def compose_api_path(api, path):
    api_path = api.path()
    for p in path:
        api_path = api_path.join(p)
    return api_path

def prepare_for_add(entry):
    new_entry = {}
    for k,v in entry.items():
        new_entry[k] = v
    return new_entry

DISABLED_MEANS_EMPTY_STRING = ('comment', )


def main():
    module_args = dict(
        bridge=dict(type='str', required=True),
        interface=dict(type='str', required=True),
        interface_type=dict(type='str'),
        tagged_vlans=dict(type='str'),
        untagged_vlan=dict(type='str'),
    )
    module_args.update(api_argument_spec())

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    check_has_library(module)
    api = create_api(module)

    path = split_path('interface bridge vlan')
    vlan_api_path = compose_api_path(api, path)
    vlan_src_data = list(vlan_api_path)

    isChanged = False

    current_interface_tagged_vlans = []
    current_interface_untagged_vlans = []
    vlans = {}
    for vlan in vlan_src_data:
      vlan_data = {}
      if 'comment' in vlan:
          vlan_data['comment'] = vlan['comment']

      vlan_data['current-tagged'] = vlan['current-tagged']
      vlan_data['current-untagged'] = vlan['current-untagged']

      vlan_data['id'] = vlan['.id']

      vlan_data['bridge'] = vlan['bridge']

      vlans[vlan['vlan-ids']] = vlan_data

      if module.params['interface'] in str(vlan['current-tagged']).split(","):
          current_interface_tagged_vlans.append(int(vlan['vlan-ids']))

      if module.params['interface'] in str(vlan['current-untagged']).split(","):
          current_interface_untagged_vlans.append(int(vlan['vlan-ids']))

    path = split_path('interface bridge port')
    port_api_path = compose_api_path(api, path)
    port_src_data = list(port_api_path)

    ports = {}
    for port in port_src_data:
        port_data = {}
        port_data['id'] = port['.id']
        port_data['frame-types'] = port['frame-types']
        port_data['pvid'] = port['pvid']
        ports[port['interface']] = port_data

    result = []

    if module.params['tagged_vlans']:
        interface_tagged_vlans = str(module.params['tagged_vlans']).split(",")
        for interface_tagged_vlan in interface_tagged_vlans:
            vlan_tagged_list = str(vlans[int(interface_tagged_vlan)]['current-tagged']).split(",")
            try:
                current_interface_tagged_vlans.remove(int(interface_tagged_vlan))
            except ValueError:
                pass
            if module.params['interface'] not in vlan_tagged_list:
                result.append(f"Adding VLAN {interface_tagged_vlan} to {module.params['interface']}")
                vlan_tagged_list.append(module.params['interface']);
                params = {'.id': vlans[int(interface_tagged_vlan)]['id'], 'tagged': ','.join(sorted(vlan_tagged_list))}
                if not module.check_mode:
                    vlan_api_path.update(**params)
                isChanged=True
            else:
                result.append(f"VLAN {interface_tagged_vlan} already on {module.params['interface']}")

    for vlan_to_remove in current_interface_tagged_vlans:
        vlan_tagged_list = str(vlans[int(vlan_to_remove)]['current-tagged']).split(",")
        vlan_tagged_list.remove(module.params['interface'])
        params = {'.id': vlans[int(vlan_to_remove)]['id'], 'tagged': ','.join(sorted(vlan_tagged_list))}
        if not module.check_mode:
            vlan_api_path.update(**params)
        isChanged=True
        result.append(f"Removing VLAN {vlan_to_remove} from {module.params['interface']}")



    if module.params['untagged_vlan'] and module.params['tagged_vlans']:
        if ports[module.params['interface']]['frame-types'] != 'admit-all' and ports[module.params['interface']]['pvid'] != module.params['untagged_vlan']:
            params = {'.id': ports[module.params['interface']]['id'], 'frame-types': 'admit-all', 'pvid': module.params['untagged_vlan']}
            if not module.check_mode:
                port_api_path.update(**params)
            isChanged=True
            result.append(f"{module.params['interface']} is TRUNK + NATIVE - setting to admit-all and adding VLAN {module.params['untagged_vlan']}")
    elif module.params['untagged_vlan']:
        if ports[module.params['interface']]['frame-types'] != 'admit-only-untagged-and-priority-tagged' and ports[module.params['interface']]['pvid'] != module.params['untagged_vlan']:
            params = {'.id': ports[module.params['interface']]['id'], 'frame-types': 'admit-only-untagged-and-priority-tagged', 'pvid': module.params['untagged_vlan']}
            if not module.check_mode:
                port_api_path.update(**params)
            isChanged=True
            result.append(f"{module.params['interface']} is ACCESS - setting to admit-only-untagged with VLAN {module.params['untagged_vlan']}")
    else:
        if ports[module.params['interface']]['frame-types'] != 'admit-only-vlan-tagged':
            params = {'.id': ports[module.params['interface']]['id'], 'frame-types': 'admit-only-vlan-tagged'}
            if not module.check_mode:
                port_api_path.update(**params)
            isChanged=True
            result.append(f"{module.params['interface']} is TRUNK no NATIVE - setting to admit-tagged")

    module.exit_json(
        changed=isChanged,
        result=result,
        vlan_data=interface_tagged_vlans
    )


if __name__ == '__main__':
    main()
