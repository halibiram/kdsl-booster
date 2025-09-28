#
# Copyright (C) 2017 OpenWrt.org
#
# This is free software, licensed under the GNU General Public License v2.
# See /LICENSE for more information.
#
include $(TOPDIR)/rules.mk

PKG_NAME:=jq
PKG_VERSION:=1.7.1

PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://github.com/jqlang/jq/releases/download/$(PKG_NAME)-$(PKG_VERSION)
PKG_HASH:=478c9ca129fd2e3443fe27314b455e211e0d8c60bc8ff7df703873deeee580c2

include $(INCLUDE_DIR)/host-build.mk

HOST_CONFIGURE_ARGS += \
	--disable-docs \
	--disable-valgrind \
	--without-oniguruma

define Host/Install
	$(INSTALL_BIN) $(HOST_BUILD_DIR)/jq $(STAGING_DIR_HOST)/bin/
endef

define Host/Clean
	rm -f $(STAGING_DIR_HOST)/bin/jq
	$(call Host/Clean/Default)
endef

$(eval $(call HostBuild))
