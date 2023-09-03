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
        name=dict(type='str', required=True),
        vlan_id=dict(type='str', required=True),
        bridge=dict(type='str', required=True),
    )
    module_args.update(api_argument_spec())

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    check_has_library(module)
    api = create_api(module)

    path = split_path('interface bridge vlan')

    api_path = compose_api_path(api, path)

    data = list(api_path)

    vlans = {}
    for vlan in data:
      vlan_data = {}
      if 'comment' in vlan:
          vlan_data['comment'] = vlan['comment']

      vlan_data['current-tagged'] = vlan['current-tagged']
      vlan_data['current-untagged'] = vlan['current-untagged']

      vlan_data['id'] = vlan['.id']

      vlan_data['bridge'] = vlan['bridge']

      vlans[vlan['vlan-ids']] = vlan_data

    if vlans.get(int(module.params['vlan_id'])) is None:
        if not module.check_mode:
            api_path.add(**prepare_for_add({'vlan-ids': module.params['vlan_id'], 'comment': module.params['name'], 'bridge': module.params['bridge']}))
        changed = True
    else:
        changed = False
        if 'comment' not in vlans[int(module.params['vlan_id'])].keys() or vlans[int(module.params['vlan_id'])]['comment'] != module.params['name']:
            params = {'comment': module.params['name'], '.id': vlans[int(module.params['vlan_id'])]['id']}
            if not module.check_mode:
                api_path.update(**params)
            changed = True
        else:
            changed = False

    module.exit_json(
        changed=changed,
        data=vlans,
    )


if __name__ == '__main__':
    main()
