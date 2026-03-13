Name:		grommunio-web
Version:	3.17
Release:	2
Source0:	https://github.com/grommunio/grommunio-web/releases/download/grommunio-web-%{version}/grommunio-web-%{version}.tar.xz
Summary:	Web mail/calendar interface for the Grommunio groupware server
URL:		https://github.com/grommunio/grommunio-web
License:	AGPL-3.0
Group:		Servers
BuildArch:	noarch
Requires:	php-gromox
Requires:	php-fpm
Requires:	php-iconv
Requires:	php-mbstring
Requires:	php-xml
Requires:	php-dom
Requires:	php-gettext
Requires:	php-ldap
Requires:	php-gd
Requires:	grommunio-mapi-header-php
Requires:	grommunio-admin-api
Requires:	nginx

%description
grommunio Web is an open-source web application and provides all the familiar
email, advanced calendaring and contact features you need to be productive.
It is the main web application for access to your productivity workspace,
including email, calendar, contacts, tasks, notes and more.

%prep
%autosetup -p1
find . -type f |xargs sed -i \
	-e 's,/var/lib/grommunio-web/session,/run/grommunio/web/session,g' \
	-e 's,/var/lib/grommunio-web/plugin_files,/srv/grommunio/web/plugin_files,g' \
	-e 's,/var/lib/grommunio-web/tmp,/run/grommunio/web/tmp,g' \
	-e 's,/var/lib/grommunio-web/sqlite,/srv/grommunio/web/sqlite,g'

%install
mkdir -p %{buildroot}%{_datadir}/grommunio-web
cp -a * %{buildroot}%{_datadir}/grommunio-web/

mkdir -p %{buildroot}%{_sysconfdir}/grommunio-web
sed -e 's,default:,unix:/run/gromox/zcore.sock,g' config.php.dist >config.php

mkdir -p %{buildroot}%{_sysconfdir}/nginx/sites-available
cat >%{buildroot}%{_sysconfdir}/nginx/sites-available/grommunio.conf <<'EOF'
server {
	listen 80;
	server_name mail.example.com;
	root /usr/share/grommunio-web;
	index index.php;

	location / {
		try_files $uri $uri/ /index.php?$args;
	}

	location ~ \.php$ {
		include fastcgi_params;
		fastcgi_pass unix:/run/php-fpm/grommunio.sock;
		fastcgi_index index.php;
		fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
	}

	location ~* ^/(Microsoft-Server-ActiveSync|RPC|Autodiscover|mapi|oab) {
		proxy_pass http://[::1]:81;
		proxy_set_header Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

		# Increase buffer size for large MAPI payloads
		proxy_buffer_size 128k;
		proxy_buffers 4 256k;
	}

	location ~* ^/.well-known/(caldav|carddav|grommunio-sync) {
		return 301 /mapi/emu/$1;
	}

	location /owa { alias /usr/share/grommunio-web; }

	location /exchange { alias /usr/share/grommunio-web; }

	location /api {
		include uwsgi_params;
		uwsgi_pass unix:/run/grommunio/admin-api.socket;
		uwsgi_param HTTP_HOST $host;
		uwsgi_param HTTP_X_REAL_IP $remote_addr;
		uwsgi_buffer_size 32k;
		uwsgi_buffers 8 32k;
	}
}
EOF

mkdir -p %{buildroot}%{_sysconfdir}
cp %{buildroot}%{_datadir}/grommunio-web/config.php.dist %{buildroot}%{_sysconfdir}/grommunio-web/config.php
ln -s ../../../%{_sysconfdir}/grommunio-web/config.php %{buildroot}%{_datadir}/grommunio-web/

mkdir -p %{buildroot}/srv/grommunio/web/sqlite-index %{buildroot}/srv/grommunio/web/plugin_files

%files
%{_datadir}/grommunio-web
%dir %{_sysconfdir}/grommunio-web
%config %{_sysconfdir}/nginx/sites-available/grommunio.conf
%config %{_sysconfdir}/grommunio-web/config.php
%dir %attr(2755,grommunio,www) /srv/grommunio
%dir %attr(2755,grommunio,www) /srv/grommunio/web
%dir %attr(2755,grommunio,www) /srv/grommunio/web/sqlite-index
%dir %attr(2755,grommunio,www) /srv/grommunio/web/plugin_files
