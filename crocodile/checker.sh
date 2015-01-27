#!/bin/bash

sha='/tmp/1'
sha_tmp='/tmp/2'
tmp_dir='/tmp/croco'
repo='https://api.github.com/repos/bioothod/crocodile'
clone_repo='https://github.com/bioothod/crocodile.git'
init='/etc/init.d/supervisord'
cron_dir='/etc/cron.d'
src_dir='/etc/crocodile'
conf_dir="${src_dir}/conf.d"
supervisor_crocodile_conf='/etc/supervisor/conf.d/crocodile.conf'
code='ororo'
flag='old'

#checking directory
dir_chk() {
        if [ ! -d $tmp_dir ]; then
                mkdir $tmp_dir
        fi
        if [ ! -d $src_dir ]; then
                mkdir $src_dir
		flag='new'
		echo 'New installation'
        fi
        if [ ! -d $conf_dir ]; then
                mkdir $conf_dir
        fi;
}

#main part which clone all staff from repo
cloner() {
        cd $tmp_dir
        git clone $clone_repo
	mkdir -p /etc/supervisor/conf.d /var/log/supervisor

	conf_changed=`diff -N crocodile/supervisord/supervisord.conf $supervisor_crocodile_conf | wc -l`
	init_changed=`diff -N crocodile/supervisord/supervisord.sh $init | wc -l`

        cp crocodile/supervisord/supervisord.conf $supervisor_crocodile_conf
	ln -sf $supervisor_crocodile_conf /etc/supervisor/conf.d/supervisor.conf
	cp crocodile/supervisord/supervisord.sh $init
	chmod 755 $init

	sender_changed=`diff -N crocodile/crocodile/sender.py /etc/crocodile/sender.py | wc -l`

	cp crocodile/cron.d/* ${cron_dir}/
        cp -r crocodile/crocodile/* ${src_dir}
        chmod -R +x ${src_dir}
        mv $sha_tmp $sha
        rm -rf $tmp_dir

	if [ $sender_changed != 0 ]; then
		kill `ps ax | grep /etc/crocodile/sender.py | grep -v grep | awk {'print $1'}`
	fi

	if [ $init_changed != 0 ]; then
		$init restart
		return
	fi

	if [ $conf_changed != 0 ]; then
		$init restart
		return
	fi
}

#checking if there is any new commits with $code word
updater() {
	if [ $flag == 'new' ]; then
		echo 'Clean installation'
		cloner
		exit 0
	fi
#checking code word in last commit
	if [[ `shasum $sha |awk {'print $1'}` != `shasum $sha_tmp |awk {'print $1'}` ]] && [ `grep $code $sha_tmp | wc -l` -ge 1 ]; then
		echo 'special word found!'
                cloner
		exit 0
	fi
}

main() {
        dir_chk
        wget -q -O $sha_tmp "${repo}/commits?per_page=1"
        updater
}

main
