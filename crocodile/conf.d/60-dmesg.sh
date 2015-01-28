#!/bin/bash

WARN='error|warning|fail|\(da[0-9]+:[a-z0-9]+:[0-9]+:[0-9]+:[0-9]+\)|Non-Fatal\ Error\ DRAM\ Controler|nf_conntrack'
IGNORE='acpi|ehci_hcd|uses\ 32-bit\ capabilities|GHES:\ Poll\ interval|acpi_throttle[0-9]:\ failed\ to\ attach\ P_CNT|aer|aer_init:\ AER\ service\ init\ fails|aer:\ probe\ of|arplookup|(at [0-9a-f]+)? rip[: ][0-9a-f]+ rsp[: ][0-9a-f]+ error[: ]|Attempt\ to\ query\ device\ size\ failed|check_tsc_sync_source\ failed|failed\ SYNCOOKIE\ authentication|igb:|ipfw:\ pullup\ failed|Marking\ TSC\|mfi|MOD_LOAD|MSI\ interrupts|nfs\ send\ error\ 32\ |NO_REBOOT|optimal|page\ allocation\ failure|PCI\ error\ interrupt|pid\ [0-9]+|rebuild|Resume\ from\ disk\ failed|rwsem_down|smb|swap_pager_getswapspace|thr_sleep|uhub[0-9]|ukbd|usbd|EDID|radeon|drm:r100_cp_init|Opts: errors=remount-ro|nf_conntrack version'
CRIT='I/O error|medium|defect|mechanical|retrying|broken|degraded|offline|failed|unconfigured_bad|conntrack:\ table\ full|Unrecovered read error|fs error|Medium Error|Drive ECC error'

crit=`dmesg -T | grep -i -E "$CRIT" | grep -v -E "$IGNORE"`
warn=`dmesg -T | grep -i -E "$WARN" | grep -v -E "$IGNORE"`

if [ x"$crit" != x"" ]; then
	echo "{'host':'`hostname -f`', 'service':'dmesg', 'metric':666, 'state': 'error', description: '$crit'}"
	exit
fi

if [ x"$warn" != x"" ]; then
	echo "{'host':'`hostname -f`', 'service':'dmesg', 'metric':666, 'state': 'error', description: '$warn'}"
	exit
fi
