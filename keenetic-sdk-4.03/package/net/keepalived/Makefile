#
# Copyright (C) 2006-2015 OpenWrt.org
#
# This is free software, licensed under the GNU General Public License v2.
# See /LICENSE for more information.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=keepalived
PKG_VERSION:=2.2.8
PKG_RELEASE:=1

PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://www.keepalived.org/software
PKG_HASH:=85882eb62974f395d4c631be990a41a839594a7e62fbfebcb5649a937a7a1bb6

PKG_LICENSE:=GPL-2.0-or-later
PKG_LICENSE_FILES:=COPYING

PKG_INSTALL:=1

include $(INCLUDE_DIR)/package.mk
include $(INCLUDE_DIR)/kernel.mk

define Package/keepalived
  SECTION:=net
  CATEGORY:=Network
  TITLE:=VRRP with failover
  URL:=http://www.keepalived.org/
  DEPENDS:= \
    +libnl-genl \
    +libnl-route \
    +libnfnetlink
endef

define Package/keepalived/description
 VRRP with failover and monitoring daemon for Linux Virtual Server (LVS) clusters.
endef

CONFIGURE_ARGS+= \
	--disable-json \
	--with-init=SYSV \
	--disable-track-process \
	--runstatedir="/var/run" \
	--disable-lvs \
	--disable-nftables \
	--disable-iptables \
	--disable-libipset-dynamic \
	--disable-vrrp-auth \
	--disable-checksum-compat \
	--disable-linkbeat \
	--disable-routes \
	--disable-hardening

define Package/keepalived/install
	$(INSTALL_DIR) $(1)/usr/sbin
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/sbin/keepalived \
		$(1)/usr/sbin/
endef

$(eval $(call BuildPackage,keepalived))
