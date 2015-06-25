#!/usr/bin/env python

############################################################################
# prepare.py
# Copyright (C) 2015  Belledonne Communications, Grenoble France
#
############################################################################
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
############################################################################

import argparse
import os
import re
import shutil
import sys
from subprocess import Popen
sys.dont_write_bytecode = True
sys.path.insert(0, 'submodules/cmake-builder')
import prepare


class IOSTarget(prepare.Target):

    def __init__(self, arch):
        prepare.Target.__init__(self, 'ios-' + arch)
        current_path = os.path.dirname(os.path.realpath(__file__))
        self.config_file = 'configs/config-ios-' + arch + '.cmake'
        self.toolchain_file = 'toolchains/toolchain-ios-' + arch + '.cmake'
        self.output = 'liblinphone-sdk/' + arch + '-apple-darwin.ios'
        self.additional_args = [
            '-DLINPHONE_BUILDER_EXTERNAL_SOURCE_PATH=' +
            current_path + '/submodules'
        ]

    def clean(self):
        if os.path.isdir('WORK'):
            shutil.rmtree(
                'WORK', ignore_errors=False, onerror=self.handle_remove_read_only)
        if os.path.isdir('liblinphone-sdk'):
            shutil.rmtree(
                'liblinphone-sdk', ignore_errors=False, onerror=self.handle_remove_read_only)


class IOSi386Target(IOSTarget):

    def __init__(self):
        IOSTarget.__init__(self, 'i386')


class IOSx8664Target(IOSTarget):

    def __init__(self):
        IOSTarget.__init__(self, 'x86_64')


class IOSarmv7Target(IOSTarget):

    def __init__(self):
        IOSTarget.__init__(self, 'armv7')


class IOSarm64Target(IOSTarget):

    def __init__(self):
        IOSTarget.__init__(self, 'arm64')


targets = {
    'i386': IOSi386Target(),
    'x86_64': IOSx8664Target(),
    'armv7': IOSarmv7Target(),
    'arm64': IOSarm64Target()
}
archs_device = ['arm64', 'armv7']
archs_simu = ['i386', 'x86_64']
platforms = ['all', 'devices', 'simulators'] + archs_device + archs_simu


class PlatformListAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        if values:
            for value in values:
                if value not in platforms:
                    message = ("invalid platform: {0!r} (choose from {1})".format(
                        value, ', '.join([repr(platform) for platform in platforms])))
                    raise argparse.ArgumentError(self, message)
            setattr(namespace, self.dest, values)


def warning(platforms):
    gpl_third_parties_enabled = False
    regex = re.compile("^ENABLE_GPL_THIRD_PARTIES:BOOL=ON")
    f = open(
        'WORK/ios-{arch}/cmake/CMakeCache.txt'.format(arch=platforms[0]), 'r')
    for line in f:
        if regex.match(line):
            gpl_third_parties_enabled = True
            break
    f.close()

    if gpl_third_parties_enabled:
        print("***************************************************************************\n"
              "***************************************************************************\n"
              "***** CAUTION, this liblinphone SDK is built using 3rd party GPL code *****\n"
              "***** Even if you acquired a proprietary license from Belledonne      *****\n"
              "***** Communications, this SDK is GPL and GPL only.                   *****\n"
              "***** To disable 3rd party gpl code, please use:                      *****\n"
              "***** $ ./prepare.py -DENABLE_GPL_THIRD_PARTIES=NO                    *****\n"
              "***************************************************************************\n"
              "***************************************************************************\n")
    else:
        print("*****************************************************************\n"
              "*****************************************************************\n"
              "***** Linphone SDK without 3rd party GPL software           *****\n"
              "***** If you acquired a proprietary license from Belledonne *****\n"
              "***** Communications, this SDK can be used to create        *****\n"
              "***** a proprietary linphone-based application.             *****\n"
              "*****************************************************************\n"
              "*****************************************************************\n")


def extract_libs_list():
    l = []
    # name = libspeexdsp.a; path = "liblinphone-sdk/apple-darwin/lib/libspeexdsp.a"; sourceTree = "<group>"; };
    regex = re.compile("name = (lib(\S+)\.a); path = \"liblinphone-sdk/apple-darwin/")
    f = open('linphone.xcodeproj/project.pbxproj', 'r')
    lines = f.readlines()
    f.close()
    for line in lines:
        m = regex.search(line)
        if m is not None:
            l += [m.group(1)]
    return list(set(l))


def install_git_hook():
    git_hook_path = ".git{sep}hooks{sep}pre-commit".format(sep=os.sep)
    if os.path.isdir(".git{sep}hooks".format(sep=os.sep)) and not os.path.isfile(git_hook_path):
        print("Installing Git pre-commit hook")
        shutil.copyfile(".git-pre-commit", git_hook_path)
        os.chmod(git_hook_path, 0755)


def generate_makefile(platforms, generator):
    libs_list = extract_libs_list()
    packages = os.listdir('WORK/ios-' + platforms[0] + '/Build')
    packages.sort()
    arch_targets = ""
    for arch in platforms:
        arch_targets += """
{arch}: all-{arch}

package-in-list-%:
\tif ! grep -q " $* " <<< " $(packages) "; then \\
\t\techo "$* not in list of available packages: $(packages)"; \\
\t\texit 3; \\
\tfi

{arch}-build:
\t@for package in $(packages); do \\
\t\t$(MAKE) {arch}-build-$$package; \\
\tdone

{arch}-clean:
\t@for package in $(packages); do \\
\t\t$(MAKE) {arch}-clean-$$package; \\
\tdone

{arch}-veryclean:
\t@for package in $(packages); do \\
\t\t$(MAKE) {arch}-veryclean-$$package; \\
\tdone

{arch}-build-%: package-in-list-%
\trm -f WORK/ios-{arch}/Stamp/EP_$*/EP_$*-update; \\
\t{generator} WORK/ios-{arch}/cmake EP_$*

{arch}-clean-%: package-in-list-%
\t{generator} WORK/ios-{arch}/Build/$* clean; \\
\trm -f WORK/ios-{arch}/Stamp/EP_$*/EP_$*-build; \\
\trm -f WORK/ios-{arch}/Stamp/EP_$*/EP_$*-install;

{arch}-veryclean-%: package-in-list-%
\tcat WORK/ios-{arch}/Build/$*/install_manifest.txt | xargs rm; \\
\trm -rf WORK/ios-{arch}/Build/$*/*; \\
\trm -f WORK/ios-{arch}/Stamp/EP_$*/*; \\
\techo "Run 'make {arch}-build-$*' to rebuild $* correctly.";

{arch}-veryclean-ffmpeg:
\t{generator} WORK/ios-{arch}/Build/ffmpeg uninstall; \\
\trm -rf WORK/ios-{arch}/Build/ffmpeg/*; \\
\trm -f WORK/ios-{arch}/Stamp/EP_ffmpeg/*; \\
\techo "Run 'make {arch}-build-ffmpeg' to rebuild ffmpeg correctly.";

{arch}-clean-openh264:
\tcd WORK/ios-{arch}/Build/openh264; \\
\t$(MAKE) -f ../../../../submodules/externals/openh264/Makefile clean; \\
\trm -f WORK/ios-{arch}/Stamp/EP_openh264/EP_openh264-build; \\
\trm -f WORK/ios-{arch}/Stamp/EP_openh264/EP_openh264-install;

{arch}-veryclean-openh264:
\trm -rf liblinphone-sdk/{arch}-apple-darwin.ios/include/wels; \\
\trm -f liblinphone-sdk/{arch}-apple-darwin.ios/lib/libopenh264.*; \\
\trm -rf WORK/ios-{arch}/Build/openh264/*; \\
\trm -f WORK/ios-{arch}/Stamp/EP_openh264/*; \\
\techo "Run 'make {arch}-build-openh264' to rebuild openh264 correctly.";

{arch}-veryclean-vpx:
\trm -rf liblinphone-sdk/{arch}-apple-darwin.ios/include/vpx; \\
\trm -f liblinphone-sdk/{arch}-apple-darwin.ios/lib/libvpx.*; \\
\trm -rf WORK/ios-{arch}/Build/vpx/*; \\
\trm -f WORK/ios-{arch}/Stamp/EP_vpx/*; \\
\techo "Run 'make {arch}-build-vpx' to rebuild vpx correctly.";
""".format(arch=arch, generator=generator)
    multiarch = ""
    for arch in platforms[1:]:
        multiarch += \
            """     if test -f "$${arch}_path"; then \\
        all_paths=`echo $$all_paths $${arch}_path`; \\
        all_archs="$$all_archs,{arch}" ; \\
    else \\
        echo "WARNING: archive `basename $$archive` exists in {first_arch} tree but does not exists in {arch} tree: $${arch}_path."; \\
    fi; \\
""".format(first_arch=platforms[0], arch=arch)
    makefile = """
archs={archs}
packages={packages}
libs_list={libs_list}
LINPHONE_IPHONE_VERSION=$(shell git describe --always)

.PHONY: all

all: build

{arch_targets}
all-%:
\t@for package in $(packages); do \\
\t\trm -f WORK/ios-$*/Stamp/EP_$$package/EP_$$package-update; \\
\tdone
\t{generator} WORK/ios-$*/cmake

build-%: package-in-list-%
\t@for arch in $(archs); do \\
\t\techo "==== starting build of $* for arch $$arch ===="; \\
\t\t$(MAKE) $$arch-build-$*; \\
\tdone

clean-%: package-in-list-%
\t@for arch in $(archs); do \\
\t\techo "==== starting clean of $* for arch $$arch ===="; \\
\t\t$(MAKE) $$arch-clean-$*; \\
\tdone

veryclean-%: package-in-list-%
\t@for arch in $(archs); do \\
\t\techo "==== starting veryclean of $* for arch $$arch ===="; \\
\t\t$(MAKE) $$arch-veryclean-$*; \\
\tdone; \\
\techo "Run 'make build-$*' to rebuild $* correctly."

build: libs sdk

clean: $(addprefix clean-,$(packages))

veryclean: $(addprefix veryclean-,$(packages))

lipo:
\tarchives=`find liblinphone-sdk/{first_arch}-apple-darwin.ios -name *.a` && \\
\tmkdir -p liblinphone-sdk/apple-darwin && \\
\tcp -rf liblinphone-sdk/{first_arch}-apple-darwin.ios/include liblinphone-sdk/apple-darwin/. && \\
\tcp -rf liblinphone-sdk/{first_arch}-apple-darwin.ios/share liblinphone-sdk/apple-darwin/. && \\
\tfor archive in $$archives ; do \\
\t\tarmv7_path=`echo $$archive | sed -e "s/{first_arch}/armv7/"`; \\
\t\tarm64_path=`echo $$archive | sed -e "s/{first_arch}/arm64/"`; \\
\t\ti386_path=`echo $$archive | sed -e "s/{first_arch}/i386/"`; \\
\t\tx86_64_path=`echo $$archive | sed -e "s/{first_arch}/x86_64/"`; \\
\t\tdestpath=`echo $$archive | sed -e "s/-debug//" | sed -e "s/{first_arch}-//" | sed -e "s/\.ios//"`; \\
\t\tall_paths=`echo $$archive`; \\
\t\tall_archs="{first_arch}"; \\
\t\tmkdir -p `dirname $$destpath`; \\
\t\t{multiarch} \\
\t\techo "[$$all_archs] Mixing `basename $$archive` in $$destpath"; \\
\t\tlipo -create $$all_paths -output $$destpath; \\
\tdone && \\
\tfor lib in {libs_list} ; do \\
\t\tif [ $${{lib:0:5}} = "libms" ] ; then \\
\t\t\tlibrary_path=liblinphone-sdk/apple-darwin/lib/mediastreamer/plugins/$$lib ; \\
\t\telse \\
\t\t\tlibrary_path=liblinphone-sdk/apple-darwin/lib/$$lib ; \\
\t\tfi ; \\
\t\tif ! test -f $$library_path ; then \\
\t\t\techo "[$$all_archs] Generating dummy $$lib static library." ; \\
\t\t\tcp -f submodules/binaries/libdummy.a $$library_path ; \\
\t\tfi \\
\tdone

libs: $(addprefix all-,$(archs)) lipo

ipa: build
\txcodebuild -configuration Release \\
\t&& xcrun -sdk iphoneos PackageApplication -v build/Release-iphoneos/linphone.app -o linphone-iphone.ipa

sdk: libs
\techo "Generating SDK zip file for version $(LINPHONE_IPHONE_VERSION)"
\tzip -r liblinphone-iphone-sdk-$(LINPHONE_IPHONE_VERSION).zip \\
\tliblinphone-sdk/apple-darwin \\
\tliblinphone-tutorials \\
\t-x liblinphone-tutorials/hello-world/build\* \\
\t-x liblinphone-tutorials/hello-world/hello-world.xcodeproj/*.pbxuser \\
\t-x liblinphone-tutorials/hello-world/hello-world.xcodeproj/*.mode1v3

pull-transifex:
\ttx pull -af

push-transifex:
\t&& ./Tools/generate_strings_files.sh && tx push -s -t -f --no-interactive

zipres:
\t@tar -czf ios_assets.tar.gz Resources iTunesArtwork

help-prepare-options:
\t@echo "prepare.py was previously executed with the following options:"
\t@echo "   {options}"

help: help-prepare-options
\t@echo ""
\t@echo "(please read the README.md file first)"
\t@echo ""
\t@echo "Available architectures: {archs}"
\t@echo "Available packages: {packages}"
\t@echo ""
\t@echo "Available targets:"
\t@echo ""
\t@echo "   * all       : builds all architectures and creates the liblinphone sdk"
\t@echo "   * zipres    : creates a tar.gz file with all the resources (images)"
\t@echo ""
\t@echo "=== Advanced usage ==="
\t@echo ""
\t@echo "   *            build-[package] : builds the package for all architectures"
\t@echo "   *            clean-[package] : clean the package for all architectures"
\t@echo ""
\t@echo "   *     [{arch_opts}]-build-[package] : builds a package for the selected architecture"
\t@echo "   *     [{arch_opts}]-clean-[package] : clean the package for the selected architecture"
\t@echo ""
\t@echo "   * sdk  : re-add all generated libraries to the SDK. Use this only after a full build."
\t@echo "   * libs : after a rebuild of a subpackage, will mix the new libs in liblinphone-sdk/apple-darwin directory"
""".format(archs=' '.join(platforms), arch_opts='|'.join(platforms),
           first_arch=platforms[0], options=' '.join(sys.argv),
           arch_targets=arch_targets, packages=' '.join(packages),
           libs_list=' '.join(libs_list), multiarch=multiarch,
           generator=generator)
    f = open('Makefile', 'w')
    f.write(makefile)
    f.close()
    warning(platforms)


def main(argv=None):
    if argv is None:
        argv = sys.argv
    argparser = argparse.ArgumentParser(
        description="Prepare build of Linphone and its dependencies.")
    argparser.add_argument(
        '-c', '-C', '--clean', help="Clean a previous build instead of preparing a build.", action='store_true')
    argparser.add_argument(
        '-d', '--debug', help="Prepare a debug build, eg. add debug symbols and use no optimizations.", action='store_true')
    argparser.add_argument(
        '-dv', '--debug-verbose', help="Activate ms_debug logs.", action='store_true')
    argparser.add_argument(
        '-f', '--force', help="Force preparation, even if working directory already exist.", action='store_true')
    argparser.add_argument(
        '-G' '--generator', help="CMake build system generator (default: Unix Makefiles).", default='Unix Makefiles', choices=['Unix Makefiles', 'Ninja'])
    argparser.add_argument(
        '-L', '--list-cmake-variables', help="List non-advanced CMake cache variables.", action='store_true', dest='list_cmake_variables')
    argparser.add_argument('platform', nargs='*', action=PlatformListAction, default=[
                           'x86_64', 'devices'], help="The platform to build for (default is 'x86_64 devices'). Space separated architectures in list: {0}.".format(', '.join([repr(platform) for platform in platforms])))

    args, additional_args = argparser.parse_known_args()
    additional_args += ["-G", args.G__generator]

    if args.debug_verbose:
        additional_args += ["-DENABLE_DEBUG_LOGS=YES"]

    install_git_hook()

    selected_platforms = []
    for platform in args.platform:
        if platform == 'all':
            selected_platforms += archs_device + archs_simu
        elif platform == 'devices':
            selected_platforms += archs_device
        elif platform == 'simulators':
            selected_platforms += archs_simu
        else:
            selected_platforms += [platform]
    selected_platforms = list(set(selected_platforms))

    if args.G__generator == 'Ninja':
        generator = 'ninja -C'
    else:
        generator = '$(MAKE) -C'

    for platform in selected_platforms:
        target = targets[platform]

        if args.clean:
            target.clean()
        else:
            retcode = prepare.run(target, args.debug, False, args.list_cmake_variables, args.force, additional_args)
            if retcode != 0:
                if retcode == 51:
                    retcode = Popen(["make", "help-prepare-options"])
                return retcode

    if args.clean:
        if os.path.isfile('Makefile'):
            os.remove('Makefile')
    elif selected_platforms:
        generate_makefile(selected_platforms, generator)

    return 0

if __name__ == "__main__":
    sys.exit(main())