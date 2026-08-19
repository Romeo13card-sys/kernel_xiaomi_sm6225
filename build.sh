#CONFIGURATION
defconfig_path=arch/arm64/configs/vendor/fog_defconfig # Must be edited
defconfig=vendor/fog_defconfig # Must be edited

#Resukisu
curl -LSs "https://raw.githubusercontent.com/ReSukiSU/ReSukiSU/main/kernel/setup.sh" | bash

#KSU ACTIVATION
echo "CONFIG_KSU=y" >> $defconfig_path

#MANUAL HOOK
echo "CONFIG_KSU_MANUAL_HOOK=y" >> $defconfig_path
wget https://raw.githubusercontent.com/xxblebleblexx/manual_hook_fix/refs/heads/main/resuki-4.19-cip-st.patch;wait;patch -p1 < resuki-4.19-cip-st.patch

#Nomount driver
curl -LSs "https://raw.githubusercontent.com/xxblebleblexx/nomount-installer/refs/heads/installer/nomount.sh" | bash -s 4.19

make O=out ARCH=arm64 $defconfig; printf "n\n2\n\n\n\nY\n" | make -j$(nproc --all) CC=clang O=out ARCH=arm64 LLVM=1 LLVM_IAS=1 LD=ld.lld AS=llvm-as AR=llvm-ar NM=llvm-nm OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump READELF=llvm-readelf STRIP=llvm-strip
