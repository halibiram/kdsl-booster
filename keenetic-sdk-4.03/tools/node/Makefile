#
# Copyright (C) 2021 Keenetic Limited
#
# This is free software, licensed under the GNU General Public License v2.
# See /LICENSE for more information.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=node
PKG_VERSION:=22.14.0

PKG_ARCH:=linux-x64
PKG_SOURCE:=$(PKG_NAME)-v$(PKG_VERSION)-$(PKG_ARCH).tar.xz
PKG_SOURCE_URL:=https://nodejs.org/dist/v$(PKG_VERSION)
PKG_HASH:=69b09dba5c8dcb05c4e4273a4340db1005abeafe3927efda2bc5b249e80437ec

HOST_BUILD_DIR:=$(BUILD_DIR_HOST)/$(PKG_NAME)-v$(PKG_VERSION)-$(PKG_ARCH)

include $(INCLUDE_DIR)/host-build.mk

define Host/Compile
	PATH=$(HOST_BUILD_DIR)/bin:$(PATH) corepack enable
endef

define Host/Install
	$(INSTALL_DIR) $(STAGING_DIR_HOST)/{bin,lib}
	$(CP) $(HOST_BUILD_DIR)/bin/{node,npm,npx,yarn} $(STAGING_DIR_HOST)/bin/
	$(CP) $(HOST_BUILD_DIR)/lib/node_modules $(STAGING_DIR_HOST)/lib/
endef

define Host/Clean
endef

$(eval $(call HostBuild))
