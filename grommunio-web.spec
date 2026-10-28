Name:		grommunio-web
Version:	5.2
Release:	1
# GitHub no longer attaches a prebuilt release tarball. This is the tag archive.
Source0:	https://github.com/grommunio/grommunio-web/archive/refs/tags/grommunio-web-%{version}.tar.gz#/grommunio-web-%{version}.tar.gz
# Production npm tree (terser, postcss, cssnano, html-minifier-terser).
# No native addons; esbuild is not required, the PGP vendor bundle is committed.
Source1:	grommunio-web-%{version}-npm.tar.zst
Summary:	Web mail/calendar interface for the Grommunio groupware server
URL:		https://github.com/grommunio/grommunio-web
License:	AGPL-3.0
Group:		Servers
BuildArch:	noarch
BuildRequires:	nodejs
# Cooker has no php package. php-cli, php-fpm, php-cgi and php-dbg all
# provide the name "php", and only php-cli ships /usr/bin/php. make deploy
# lints with `php -l`, and the session cleaner calls php at runtime.
BuildRequires:	php-cli
BuildRequires:	gettext
BuildRequires:	make
BuildRequires:	python
Requires:	php-cli
Requires:	php-gromox
Requires:	php-fpm
Requires:	php-iconv
Requires:	php-mbstring
Requires:	php-xml
Requires:	php-dom
Requires:	php-gettext
Requires:	php-ldap
Requires:	php-gd
Requires:	grommunio-mapi-header-php >= 2.4
Requires:	grommunio-admin-api
Requires:	nginx

%description
grommunio Web is an open-source web application and provides all the familiar
email, advanced calendaring and contact features you need to be productive.
It is the main web application for access to your productivity workspace,
including email, calendar, contacts, tasks, notes and more.

%prep
%autosetup -n grommunio-web-grommunio-web-%{version} -p1 -a1
# The tag archive has no git metadata, so git describe cannot name the build.
python - <<'PY'
from pathlib import Path
p = Path("Makefile")
t = p.read_text()
t = t.replace(
    "$(shell git describe --abbrev=7 --always --long | sed 's/grommunio-web-//')",
    "$(shell cat version)")
old = "\tgit describe --abbrev=7 --always  --long | sed 's#grommunio-web-##' > $@"
new = "\tcat $< > $@"
if old not in t:
    raise SystemExit("grommunio-web Makefile version recipe not found")
p.write_text(t.replace(old, new, 1))
PY
find . -path ./node_modules -prune -o -type f -print0 | xargs -0 sed -i \
	-e 's,/var/lib/grommunio-web/session,/run/grommunio/web/session,g' \
	-e 's,/var/lib/grommunio-web/tmp,/run/grommunio/web/tmp,g' \
	-e 's,/var/lib/grommunio-web,/srv/grommunio/web,g'

%build
make %{?_smp_mflags} deploy

%install
mkdir -p %{buildroot}%{_datadir}/grommunio-web
cp -a deploy/. %{buildroot}%{_datadir}/grommunio-web/
rm -f %{buildroot}%{_datadir}/grommunio-web/debug.php.dist

mkdir -p %{buildroot}%{_sysconfdir}/grommunio-web
sed -e 's,default:,unix:/run/gromox/zcore.sock,g' \
	%{buildroot}%{_datadir}/grommunio-web/config.php.dist \
	>%{buildroot}%{_sysconfdir}/grommunio-web/config.php

mkdir -p %{buildroot}%{_sysconfdir}/nginx/sites-available
mkdir -p %{buildroot}%{_sysconfdir}/nginx/grommunio.d
# nginx 'include *.conf' fails if the directory is empty
cat >%{buildroot}%{_sysconfdir}/nginx/grommunio.d/00-placeholder.conf <<'EOF'
# Drop-in directory for grommunio-sync / grommunio-dav location snippets.
# This file exists so nginx can include the glob when no extras are installed.
EOF
cat >%{buildroot}%{_sysconfdir}/nginx/sites-available/grommunio.conf <<'EOF'
server {
	listen 80;
	server_name mail.example.com;
	root /usr/share/grommunio-web;
	index index.php;

	# Optional drop-ins from grommunio-sync / grommunio-dav
	include /etc/nginx/grommunio.d/*.conf;

	location / {
		try_files $uri $uri/ /index.php?$args;
	}

	client_max_body_size 50m;

	location ~* \.(?:js|mjs|css|map|gif|jpe?g|png|svg|ico|woff2?|ttf|webmanifest)$ {
		add_header Cache-Control "public, max-age=5184000";
		access_log off;
		try_files $uri =404;
	}

	location ~ \.php$ {
		include fastcgi_params;
		fastcgi_pass unix:/run/php-fpm/grommunio.sock;
		fastcgi_index index.php;
		fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
		fastcgi_read_timeout 360s;
		fastcgi_buffers 256 16k;
		fastcgi_buffer_size 16k;
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

ln -sfn %{_sysconfdir}/grommunio-web/config.php %{buildroot}%{_datadir}/grommunio-web/config.php

mkdir -p %{buildroot}/srv/grommunio/web/sqlite-index %{buildroot}/srv/grommunio/web/templates

install -D -m 0755 build/grommunio-web-session-cleanup \
	%{buildroot}%{_libexecdir}/grommunio-web/session-cleanup
install -d %{buildroot}%{_unitdir}
sed -e 's/^User=.*/User=www/' -e 's/^Group=.*/Group=www/' \
	build/grommunio-web-session-cleanup.service \
	>%{buildroot}%{_unitdir}/grommunio-web-session-cleanup.service
cp build/grommunio-web-session-cleanup.timer %{buildroot}%{_unitdir}/
install -d %{buildroot}%{_prefix}/lib/systemd/system-preset
cat >%{buildroot}%{_prefix}/lib/systemd/system-preset/50-grommunio-web.preset <<'EOF'
enable grommunio-web-session-cleanup.timer
EOF

%files
%{_datadir}/grommunio-web
%{_libexecdir}/grommunio-web
%{_unitdir}/grommunio-web-session-cleanup.service
%{_unitdir}/grommunio-web-session-cleanup.timer
%{_prefix}/lib/systemd/system-preset/50-grommunio-web.preset
%dir %{_sysconfdir}/grommunio-web
%dir %{_sysconfdir}/nginx/grommunio.d
%config(noreplace) %{_sysconfdir}/nginx/grommunio.d/00-placeholder.conf
%config %{_sysconfdir}/nginx/sites-available/grommunio.conf
%config %{_sysconfdir}/grommunio-web/config.php
%dir %attr(2755,grommunio,www) /srv/grommunio/web/sqlite-index
%dir %attr(2755,grommunio,www) /srv/grommunio/web/templates
