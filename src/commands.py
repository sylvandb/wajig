#
# WAJIG - Debian Package Management Front End
#
# Implementation of all commands
#
# Copyright (c) Graham.Williams@togaware.com
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

import os
import re
import sys
import tempfile
import signal

import apt_pkg
import apt

# wajig modules
import changes
import perform
import util
import debfile

# When writing to a pipe where there is no reader (e.g., when
# output is directed to head or to less and the user exists from less
# before reading all output) the SIGPIPE signal is generated. Capture
# the signal and hadle it with the default handler.
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

available_file = changes.available_file
previous_file  = changes.previous_file


def ping_host(hostname):
    "Check if host is reachable."

    # Check if fping is installed.
    if perform.execute("fping localhost 2>/dev/null >/dev/null",
                       display=False) != 0:
        print("fping was not found. " +\
              "Consider installing the package fping.\n")

    # Check if we can talk to the HOST
    elif perform.execute("fping " + hostname + " 2>/dev/null >/dev/null",
                         display=False) != 0:
        print("Could not contact the Debian server at " + hostname\
        + """
             Perhaps it is down or you are not connected to the network.
             JIG will continue to try to get the information required.""")
    else:
        return True  # host found


def do_force(packages):
    """Force the installation of a package.

    This is useful when there is a conflict of the same file from
    multiple packages or when a dependency is not installed for
    whatever reason.
    """
    #
    # The basic function is to force install the package using dpkg.
    #
    command = "dpkg --install --force overwrite --force depends "
    archives = "/var/cache/apt/archives/"
    #
    # For a .deb file we simply force install it.
    #
    if re.match(".*\.deb$", packages[0]):
        for package in packages:
            if os.path.exists(package):
                command += "'" + package + "' "
            elif os.path.exists(archives + package):
                command += "'" + archives + package + "' "
            else:
                print("""File `%s' not found.
              Searched current directory and %s.
              Please confirm the location and try again.""" % (package, archives))
                return()
    else:
        #
        # Package names rather than a specific deb package archive
        # is expected.
        #
        for package in packages:
            #
            # Identify the latest version of the package available in
            # the download archive, if there is any there.
            #
            lscmd = "/bin/ls " + archives
            lscmd += " | egrep '^" + package + "_' | sort -k 1b,1 | tail -n -1"
            matches = perform.execute(lscmd, pipe=True)
            debpkg = matches.readline().strip()
            #
            # If the package was not perfound then download it before
            # it is force installed.
            #
            if not debpkg:
                dlcmd = "apt-get --quiet=2 --reinstall --download-only "
                dlcmd += "install '" + package + "'"
                perform.execute(dlcmd, root=1)
                matches = perform.execute(lscmd, pipe=True)
                debpkg = matches.readline().strip()
            #
            # Force install the package from the download archive.
            #
            command += "'" + archives + debpkg + "' "
    #
    # The command has been built.  Now execute it.
    #
    perform.execute(command, root=1)


def do_install(packages, yes="", noauth="", dist=""):
    "Install packages."

    #
    # Currently we use the first argument to determine the type of all
    # of the rest. Perhaps we should look at each one in turn?
    #

    #
    # Handle URLs first. We don't do anything smart.  Simply download
    # the .deb file and install it.  If it fails then don't attempt to
    # recover.  The user can do a wget themselves and install the
    # resulting .deb if they need to.
    #
    # Currently only a single URL is allowed. Should this be generalised?
    #

    # reading packages from stdin
    if len(packages) == 1 and packages[0] == "-":
        stripped = [x.strip() for x in sys.stdin.readlines()]
        joined = str.join(stripped)
        packages = joined.split()

    # reading packages from a file
    elif len(packages) == 2 and packages[0] == "-f":
        stripped = [x.strip() for x in open(packages[1]).readlines()]
        joined = str.join(stripped)
        packages = str.split(joined)

    # check if a specific web location was specified
    if re.match("(http|ftp)://", packages[0]) \
       and util.requires_package("wget", "/usr/bin/wget"):
        if len(packages) > 1:
            print("install URL allows only one URL, not " +\
                  str(len(packages)))
            sys.exit(1)
        tmpdeb = tempfile.mkstemp()[1] + ".deb"
        command = "wget --output-document=" + tmpdeb + " " + packages[0]
        if not perform.execute(command):
            command = "dpkg --install " + tmpdeb
            perform.execute(command, root=1)
            if os.path.exists(tmpdeb):
                os.remove(tmpdeb)
        else:
            print("The location " + packages[0] +\
                  " was not found. Check and try again.")

    # check if DEB files were specified
    elif re.match(".*\.deb$", packages[0]):
        debfile.install(set(packages))
    #
    # Check if a "/+" is in a package name then use the following distribution
    # for all packages! We might not want this previsely if there are multiple
    # packages listed and only one has the /+ notation. So do it only for the
    # specified one. I have introduced this notation myself, extending
    # the apt-get "/" notation. "+" by itself won't work since "+" can
    # appear in a package name, and it is okay if a distribution name starts
    # with "+" since you just include two "+"'s then.
    #
    # TODO
    #
    # Currently only do this for the first package........
    #
#     elif re.match(".*/+.*", packages[0]):
#         print "HI"
#         (packages[0], release) = re.compile(r'/\+').split(packages[0])
#       command = "apt-get --target-release %s install %s" %\
#                   (release, util.concat(packages))
#       perform.execute(command, root=1)
    else:
        rec = util.recommends()
        if dist:
            dist = "--target-release " + dist
        command = "apt-get {0} {1} {2} {3} install {4}"
        command = command.format(yes, noauth, rec, dist, " ".join(packages))
        perform.execute(command, root=True)


def do_install_suggest(package_name, yes, noauth):
    """Install a package and its Suggests dependencies"""
    cache = apt.cache.Cache()
    try:
        package = cache[package_name]
    except KeyError as error:
        print(error.args[0])
        sys.exit(1)
    dependencies = " ".join(util.extract_dependencies(package, "Suggests"))
    template = "apt-get {0} {1} {2} --show-upgraded install {3} {4}"
    command = template.format(util.recommends(), yes, noauth, dependencies,
                          package_name)
    perform.execute(command, root=True)


def do_listsections():
    cache = apt.cache.Cache()
    sections = list()
    for package in cache.keys():
        package = cache[package]
        sections.append(package.section)
    sections = set(sections)
    for section in sections:
        print(section)


def do_listsection(section):
    cache = apt.cache.Cache()
    for package in cache.keys():
        package = cache[package]
        if(package.section == section):
            print(package.name)


def do_listinstalled(pattern):
    "Display a list of installed packages."
    command = "dpkg --get-selections | awk '$2 ~/^install$/ {print $1}'"
    if len(pattern) == 1:
        command = command + " | grep -- " + pattern[0] + " | sort -k 1b,1"
    perform.execute(command)


def do_listnames(pattern, pipe=False):
    "Print list of known package names."

    # If user can't access /etc/apt/sources.list then must do this with
    # sudo or else most packages will not be found.
    needsudo = not os.access("/etc/apt/sources.list", os.R_OK)
    if len(pattern) == 0:
        command = "apt-cache pkgnames | sort -k 1b,1"
    else:
        command = "apt-cache pkgnames | grep -- " + pattern[0] \
                + " | sort -k 1b,1"
    # Start fix for Bug #292581 - pre-run command to check for no output
    results = perform.execute(command, root=needsudo, pipe=True).readlines()
    if len(results) == 0:
        sys.exit(1)
    # End fix for Bug #292581
    return perform.execute(command, root=needsudo, pipe=pipe)


def do_listscripts(package):
    scripts = ["preinst", "postinst", "prerm", "postrm"]
    if re.match(".*\.deb$", package):
        command = "ar p " + package + " control.tar.gz | tar ztvf -"
        pkgScripts = perform.execute(command, pipe=True).readlines()
        for script in scripts:
            if "./" + script in "".join(pkgScripts):
                nlen = (72 - len(script)) / 2
                print(">"*nlen, script, "<"*nlen)
                command = "ar p " + package + " control.tar.gz |" +\
                          "tar zxvf - -O ./" + script +\
                          " 2>/dev/null"
                perform.execute(command)
    else:
        root = "/var/lib/dpkg/info/"
        for script in scripts:
            fname = root + package + "." + script
            if os.path.exists(fname):
                nlen = (72 - len(script))/2
                print(">"*nlen, script, "<"*nlen)
                perform.execute("cat " + fname)


def do_new():
    "Report on packages that are newly available."

    print("%-24s %s" % ("Package", "Available"))
    print("="*24 + "-" + "="*16)
    #
    # List each package and it's version
    #
    new_packages = changes.get_new_available()
    new_packages.sort()
    for i in range(0, len(new_packages)):
        print("%-24s %s" % (new_packages[i],
            changes.get_available_version(new_packages[i])))


def do_newupgrades(install=False):
    "Display packages that are newly upgraded."

    #
    # Load the dictionaries from file then list each one and it's version
    #
    new_upgrades = changes.get_new_upgrades()
    if len(new_upgrades) == 0:
        print("No new upgrades")
    else:
        print("%-24s %-24s %s" % ("Package", "Available", "Installed"))
        print("="*24 + "-" + "="*24 + "-" + "="*24)
        new_upgrades.sort()
        for i in range(0, len(new_upgrades)):
            print("%-24s %-24s %-24s" % (new_upgrades[i], \
                            changes.get_available_version(new_upgrades[i]), \
                            changes.get_installed_version(new_upgrades[i])))
        if install:
            print("="*74)
            do_install(new_upgrades)


def do_size(packages, size=0):
    "Print sizes for package in list PACKAGES with size greater than SIZE."

    # Work with the list of installed packages
    # (I think status has more than installed?)
    status = apt_pkg.TagFile(open("/var/lib/dpkg/status", "r"))
    size_list = dict()
    status_list = dict()

    # Check for information in the Status list
    for section in status:
        if not packages or section.get("Package") in packages:
            package_name   = section.get("Package")
            package_size   = section.get("Installed-Size")
            package_status = re.split(" ", section.get("Status"))[2]
            if package_size and int(package_size) > size:
                if package_name not in size_list:
                    size_list[package_name] = package_size
                    status_list[package_name] = package_status

    packages = list(size_list)
    packages.sort(key=lambda x: int(size_list[x]))  # sort by size

    if len(packages) == 0:
        print("No packages found from those known to be available or installed")
    else:
        print("{:<33} {:^10} {:>12}".format("Package", "Size (KB)", "Status"))
        print("{}-{}-{}".format("="*33, "="*10, "="*12))
        for package in packages:
            print("{:<33} {:^10} {:>12}".format(package,
                    format(int(size_list[package]), ',d'), status_list[package]))


def do_status(packages, snapshot=False):
    """List status of the packages identified.

    Arguments:
    packages    List the version of installed packages
    snapshot    Whether a snapshot is required (affects output format)
    """

    if not snapshot:
        print("%-23s %-15s %-15s %-15s %s" % \
              ("Package", "Installed", "Previous", "Now", "State"))
        print("="*23 + "-" + "="*15 + "-" + "="*15 + "-" + "="*15 + "-" + "="*5)
        sys.stdout.flush()
    #
    # Get status.  Previously used dpkg --list but this truncates package
    # names to 16 characters :-(. Perhaps should now also remove the DS
    # column as that was the "ii" thing from dpkg --list.  It is now
    # "install" or "deinstall" from dpkg --get-selections.
    #
    #   command = "dpkg --list | " +\
    #             "awk '{print $2,$1}' | " +\
    #
    # Generate a temporary file of installed packages.
    #
    ifile = tempfile.mkstemp()[1]
    #
    # Using langC=TRUE here makes it work for other LANG, e.g.,
    # LANG=ru_RU.koi8r. Seems that the sorting is the key problem. To
    # test, try:
    #
    #   $ wajign status | wc -l
    #   1762
    #   $ LANG=ru_RU.koi8r wajign status | wc -l
    #   1762
    #
    # But now set it to False (the default):
    #
    #   $ LANG=ru_RU.koi8r wajign status | wc -l
    #   1449
    #
    # See Bug#288852 and Bug#119899.
    #
    perform.execute(changes.gen_installed_command_str() + " > " + ifile,
                    langC=True)
    #
    # Build the command to list the status of installed packages.
    #
    command = "dpkg --get-selections | join - " + ifile + " | " +\
              "join -a 1 - " + previous_file + " | " +\
              "awk 'NF==3 {print $0, \"N/A\"; next}{print}' | " +\
              "join -a 1 - " + available_file + " | " +\
              "awk 'NF==4 {print $0, \"N/A\"; next}{print}' | "
    if len(packages) > 0:
        # Use grep, not egrep, otherwise g++ gets lost, for example!
        command = command + "grep '^\($"
        for i in packages:
            command = command + " \|" + i
        command = command + " \)' |"

    command = command +\
              "awk '{printf(\"%-20s\\t%-15s\\t%-15s\\t%-15s\\t%-2s\\n\", " +\
              "$1, $3, $4, $5, $2)}'"
    if snapshot:
        fobj = perform.execute(command, pipe=True)
        for l in fobj:
            print("=".join(l.split()[0:2]))
    else:
        perform.execute(command, langC=True)
    #
    # Check whether the package is not in the installed list, and if not
    # list its status appropriately.
    #
    for i in packages:
        if perform.execute("egrep '^" + i + " ' " + ifile + " >/dev/null"):
            # Package is not installed.
            command = \
              "join -a 2 " + previous_file + " " + available_file + " | " +\
              "awk 'NF==2 {print $1, \"N/A\", $2; next}{print}' | " +\
              "egrep '^" + i + " '"
            command = command +\
              " | awk '{printf(\"%-20s\\t%-15s\\t%-15s\\t%-15s\\n\", " +\
              "$1, \"N/A\", $2, $3)}'"
            perform.execute(command, langC=True)

    # Tidy up - remove the "installed file"
    if os.path.exists(ifile):
        os.remove(ifile)


def do_toupgrade():
    "List packages with Available version more recent than Installed."

    # A simple way of doing this is to just list packages in the installed
    # list and the available list which have different versions.
    # However this does not capture the situation where the available
    # package version predates the installed package version (e.g,
    # you've installed a more recent version than in the distribution).
    # So now also add in a call to "dpkg --compare-versions" which slows
    # things down quite a bit!
    print("%-24s %-24s %s" % ("Package", "Available", "Installed"))
    print("="*24 + "-" + "="*24 + "-" + "="*24)

    # List each upgraded pacakge and it's version.
    to_upgrade = changes.get_to_upgrade()
    to_upgrade.sort()
    for i in range(0, len(to_upgrade)):
        print("%-24s %-24s %-24s" % (to_upgrade[i], \
                            changes.get_available_version(to_upgrade[i]), \
                            changes.get_installed_version(to_upgrade[i])))


def do_unhold(packages):
    "Remove packages from hold (they will again be upgraded)."

    for package in packages:
        # The dpkg needs sudo but not the echo.
        # Do all of it as root then.
        command = "echo \"" + package + " install\" | dpkg --set-selections"
        perform.execute(command, root=1)
    print("The following packages are still on hold:")
    perform.execute("dpkg --get-selections | egrep 'hold$' | cut -f1")


def do_update():
    if not perform.execute("apt-get update", root=1):
        changes.update_available()
        print("There are " + changes.count_upgrades() + " new upgrades")


def do_findpkg(package):
    "Look for a particular package at apt-get.org."

    ping_host("www.apt-get.org")

    # Print out a suitable heading
    print("Lines suitable for /etc/apt/sources.list\n")
    sys.stdout.flush()

    # Obtain the information from the Apt-Get server
    results = tempfile.mkstemp()[1]
    command = "wget --timeout=60 --output-document=" + results +\
              " http://www.apt-get.org/" +\
              "search.php\?query=" + package +\
              "\&submit=\&arch%5B%5D=i386\&arch%5B%5D=all " +\
              "2> /dev/null"
    perform.execute(command)

    # A single page of output
    command = "cat " + results + " | " +\
              "egrep '(^deb|sites and .*packages)' | " +\
              "perl -p -e 's|<[^>]*>||g;s|<[^>]*$||g;s|^[^<]*>||g;'" +\
              "| awk '/^deb/{" +\
              'print "\t", $0;next}/ sites and /' +\
              '{printf "\\n" ;' +\
              "print}'"
    perform.execute(command)

    if os.path.exists(results):
        os.remove(results)


def do_recdownload(packages):
    #FIXME: This has problems with virtual packages, FIX THEM!!!

    """Download packages and all dependencies recursively.
    Author: Juanjo Alvarez <juanjux@yahoo.es>
    """

    def get_deps(package):
        tagfile = apt_pkg.TagFile(open("/var/lib/dpkg/available", "r"))
        deplist = []
        for section in tagfile:
            if section.get("Package") == package:
                deplist = apt_pkg.parse_depends(section.get("Depends", ""))
                break
        realdeplist = []
        if deplist != []:
            for i in deplist:
                realdeplist.append((i[0][0], i[0][1]))
        return realdeplist

    def get_deps_recursively(package, packageslist):
        if not package in packageslist:
            packageslist.append(package)
        for packageName, versionInfo in get_deps(package):
            if packageName not in packageslist:
                packageslist.append(packageName)
                get_deps_recursively(packageName, packageslist)
        return packageslist

    package_names = []
    dontDownloadList = []
    for package in packages[:]:
        # Ignore packages with a "-" at the end so the user can workaround some
        # dependencies problems (usually in unstable)
        if package[len(package) - 1:] == "-":
            dontDownloadList.append(package[:-1])
            packages.remove(package)
            continue

    print("Calculating all dependencies...")
    for i in packages:
        tmp = get_deps_recursively(i, [])
        for i in tmp:
            # We don't want dupplicated package names
            # and we don't want package in the dontDownloadList
            if i in dontDownloadList:
                continue
            if i not in package_names:
                package_names.append(i)
    print("Packages to download to /var/cache/apt/archives:")
    for i in package_names:
        # We do this because apt-get install dont list the packages to
        # reinstall if they don't need to be upgraded
        print(i, end=' ')
    print("\n")

    command = "apt-get --download-only --reinstall -u install " + \
              " ".join(package_names)
    perform.execute(command, root=1)


def versions(packages):
    if len(packages) == 0:
        perform.execute("apt-show-versions")
    else:
        for package in packages:
            perform.execute("apt-show-versions " + package)


def addcdrom(command, args):
    """
    Add a Debian CD/DVD to APT's list of available sources
    $ wajig addcdrom
    
    note: this runs 'apt-cdrom add'
    """
    util.requires_no_args(command, args)
    perform.execute("apt-cdrom add", root=True)


def addrepo(command, args):
    """
    Add a Launchpad PPA (Personal Package Archive) repository.
    Here's an example that shows how to add the daily builds of
    Google's Chromium browser:
    $ wajig addrepo ppa:chromium-daily      (add-apt-repository)
    """
    util.requires_one_arg(command, args,
                         "a PPA (Personal Package Archive) repository to add")
    util.requires_package("add-apt-repository", "/usr/bin/add-apt-repository")
    perform.execute("add-apt-repository " + args[1], root=True)


def autoalts(command, args):
    """
    Mark the Alternative to be auto-set (using set priorities).
    $ wajig autoalts <alternative name>

    note: this runs 'update-alternatives --auto'
    """
    util.requires_one_arg(command, args, "name alternative to set as auto")
    perform.execute("update-alternatives --auto " + args[1], root=True)


def autodownload(args, verbose):
    """
    Do an update followed by a download of all updated packages.
    $ wajig autodownload
    
    note: this runs 'apt-get -d -u -y dist-upgrade'
    """
    util.requires_no_args("autodownload", args)
    if verbose:
        do_update()
        filter_str = ""
    else:
        do_update()
        filter_str = '| egrep -v "(http|ftp)"'
    perform.execute("apt-get --download-only --show-upgraded " + \
                    "--assume-yes dist-upgrade " + filter_str,
                    root=True)
    util.do_describe_new(verbose)
    do_newupgrades()


def autoclean(args):
    """
    Remove no-longer-downloadable .deb files from the download cache.
    $ wajig autoclean

    note: this runs 'apt-get autoclean'
    """
    util.requires_no_args("autodownload", args)
    perform.execute("apt-get autoclean", root=True)


def autoremove(args):
    """
    Remove unused dependency packages
    $ wajig autoremove
    """
    util.requires_no_args("autoremove", args)
    perform.execute("apt-get autoremove", root=True)


def reportbug(args):
    """
    Report a bug in a package using Debian BTS (Bug Tracking System).
    $ wajig bug <package name>

    note: this runs 'reportbug'
    """
    util.requires_one_arg("reportbug", args, "a single named package")
    util.requires_package("reportbug", "/usr/bin/reportbug")
    # 090430 Specify bts=debian since ubuntu not working at present
    perform.execute("reportbug --bts=debian " + args[1])


def build(args, yes, noauth):
    """
    Retrieve source packages, unpack them, and build binary (.deb) packages
    from them. This also installs the needed build-dependencies if needed.
    $ wajig buld <package names>
    options:
      -n --noauth       install and build even if package(s) is untrusted
      -y --yes          install/download without yes/no prompts; use with care!

    note: this runs 'apt-get build-dep && apt-get source --build'
    """
    util.requires_args("build", args, "a list of package names")
    util.requires_package("sudo", "/usr/bin/sudo")
    # First make sure dependencies are met
    command = "apt-get {} {} build-dep " + " ".join(args[1:])
    command = command.format(yes, noauth)
    result = perform.execute(command, root=True)
    if not result:
        command = "apt-get {} source --build " + " ".join(args[1:])
        command = command.format(noauth)
        perform.execute(command, root=True)


def builddeps(args, yes, noauth):
    """
    Install build-dependencies for given packages.
    $ wajig builddep <package names>

    long form command: reverse-build-depends

    options:
      -n --noauth       install even if package is untrusted
      -y --yes          install without yes/no prompts; use with care!

    note: this runs 'apt-get build-dep'
    """
    util.requires_args("builddepend", args, "a list of package names")
    command = "apt-get {} {} build-dep " + " ".join(args[1:])
    command = command.format(yes, noauth)
    perform.execute(command, root=True)


def rbuilddeps(args):
    """
    Display the packages which build-depend on the given package.
    $ wajig rbuilddeps PKG
    """
    util.requires_one_arg("rbuilddeps", args, "one package name")
    util.requires_package("grep-dctrl", "/usr/bin/grep-dctrl")
    command = "grep-available -sPackage -FBuild-Depends,Build-Depends-Indep "
    command = command + args[1] + " /var/lib/apt/lists/*Sources"
    perform.execute(command)


def changelog(args, verbose):
    """
    Display Debian changelog of a package.
    $ wajig changelog <package name>
    options:
    network on:
         changelog - if there's newer entries, display them
      -v changelog - if there's newer entries, display them, and proceed to
                     display complete local changelog

    network off:
         changelog - if there's newer entries, mention failure to retrieve
      -v changelog - if there's newer entries, mention failure to retrieve, and
                     proceed to display complete local changelog
    """
    util.requires_one_arg("changelog", args, "one package name")
    package_name = args[1]
    util.package_exists(package_name)

    changelog = "{:=^79}\n".format(" {} ".format(package_name))  # header

    package = apt.Cache()[package_name]
    try:
        changelog += package.get_changelog()
    except AttributeError as e:
        # This is caught so as to avoid an ugly python-apt trace; it's a bug
        # that surfaces when:
        # 1. The package is not available in the default Debian suite
        # 2. The suite the package belongs to is set to a pin of < 0
        print("If this package is not on your default Debian suite, " \
              "ensure that it's APT pinning isn't less than 0.")
        return
    help_message = "\nTo display the local changelog, run:\n" \
                   "wajig --verbose changelog " + package_name
    if "Failed to download the list of changes" in changelog:
        if not verbose:
            changelog += help_message
        else:
            changelog += "\n"
    elif changelog.endswith("The list of changes is not available"):
        changelog += ".\nYou are likely running the latest version.\n"
        if not verbose:
            changelog += help_message
    if not verbose:
        print(changelog)
    else:
        tmp = tempfile.mkstemp()[1]
        with open(tmp, "w") as f:
            if package.is_installed:
                changelog += "{:=^79}\n".format(" local changelog ")
            f.write(changelog)
        if package.is_installed:
            command = util.local_changelog(package_name, tmp)
            if not command:
                return
            perform.execute(command)
        with open(tmp) as f:
            for line in f:
                sys.stdout.write(line)


def clean(args):
    """
    Remove all deb files from the download cache.
    $ wajig clean

    note: this runs 'apt-get clean'
    """
    util.requires_no_args("clean", args)
    perform.execute("apt-get clean", root=True)


def contents(args):
    """
    List the contents of a package file (.deb).
    $ wajig contents <deb file>
    
    note: this runs 'dpkg --contents'
    """
    util.requires_one_arg("contents", args, "a single filename")
    perform.execute("dpkg --contents " + args[1])


def dailyupgrade(args):
    """
    Perform an update then a dist-upgrade.
    $ wajg daily-upgrade
    
    note: this runs 'apt-get --show-upgraded dist-upgrade'
    """
    util.requires_no_args("dailyupgrade", args)
    do_update()
    perform.execute("apt-get --show-upgraded dist-upgrade", root=True)


def dependents(args):
    """
    Display packages which have some form of dependency on the given package.

    Types of dependencies:
    * Depends
    * Recommends
    * Suggests
    * Replaces
    * Enhances

    $ wajig dependents <package name>
    """
    util.requires_one_arg("dependents", args, "one package name")
    package = args[1]

    DEPENDENCY_TYPES = [
        "Depends",
        "Recommends",
        "Suggests",
        "Replaces",
        "Enhances",
    ]

    cache = apt.cache.Cache()
    try:
        package = cache[package]
    except KeyError as error:
        print(error.args[0])
        sys.exit(1)

    dependents = { name : [] for name in DEPENDENCY_TYPES }

    for key in cache.keys():
        other_package = cache[key]
        for dependency_type, specific_dependents in dependents.items():
            if package.shortname in util.extract_dependencies(other_package, dependency_type):
                specific_dependents.append(other_package.shortname)

    for dependency_type, specific_dependents in dependents.items():
        if specific_dependents:
            output = dependency_type.upper(), " ".join(specific_dependents)
            print("{}: {}".format(*output))


def describe(args, verbose):
    """
    Display the short description of a package(s).
    $ wajig describe <package name>
    options:
      -v  --verbose     display long description as well
    """
    util.requires_args("describe", args, "a list of packages")
    util.do_describe(args[1:], verbose)


def describenew(args, verbose):
    """
    One line descriptions of new packages.
    $ wajig describe-new
    """
    util.requires_no_args("describe", args)
    util.do_describe_new(verbose)


def newdetail(args):
    """
    Provide a detailed description of new packages.
    $ wajig detail-new
    """
    util.requires_no_args("newdetail", args)
    new_packages = changes.get_new_available()
    if new_packages:
        package_names = " ".join(new_packages)
        command = "apt-cache" if util.fast else "aptitude"
        perform.execute("{} show {}".format(command, package_names))
    else:
        print("No new packages available")




def help(args):
    """
    Print help on individual command.
    $ wajig help COMMAND
    """
    util.requires_args("help", args, "wajig commands(s)")
    for command in args[1:]:
        if command == "autoalternatives":
            command = "autoalts"
        elif command in "builddepend builddepends builddeps".split():
            command = "builddeps"
        elif command in ["rbuilddep", "reversebuilddeps",
                         "reversebuilddependencies"]:
            command = "rbuilddeps"
        elif command == "newdescribe":
            command = "describenew"
        elif command == "detailnew":
            command = "newdetail"
        elif command in ["detail", "details"]:
            command = "show"
        util.help(command)


def hold(args):
    """
    Place packages on hold (so they will not be upgraded).
    $ wajig hold <package names>
    """
    util.requires_args("hold", args, "a list of packages to place on hold")
    for package in args[1:]:
        # The dpkg needs sudo but not the echo.
        # Do all of it as root then!
        command = "echo \"" + package + " hold\" | dpkg --set-selections"
        perform.execute(command, root=True)
    print("The following packages are on hold:")
    perform.execute("dpkg --get-selections | egrep 'hold$' | cut -f1")


def show(args):
    """
    Provide a detailed description of package (describe -vv).
    $ wajig detail <package names>
    options:
      -f --fast     use apt-cache's version of SHOW, due to its speed; see
                    debian/changelog for 2.0.50 release for the rationale on
                    why aptitude's version was chosen as default
    """
    util.requires_args("show", args, "a list of packages or package file")
    package_names = " ".join(set(args[1:]))
    tool = "apt-cache" if util.fast else "aptitude"
    command = "{} show {}".format(tool, package_names)
    perform.execute(command)

def upgrade(args, yes, noauth):
    """
    Conservative system upgrade... won't remove or install new packages
    $ wajig upgrade
    options:
      -b --backup   backup packages about to be upgraded onto some default directory
      -n --noauth   skip the authentication verification prompt before the upgrade
      -y --yes      to skip confirmation prompts (warning: not safe)
    """
    util.requires_no_args("upgrade", args)
    packages = util.upgradable()
    if packages:
        if backup:
            util.requires_package("dpkg-repack", "/usr/bin/dpkg-repack")
            util.requires_package("fakeroot", "/usr/bin/fakeroot")
            changes.backup_before_upgrade(packages)
        command = "apt-get {0} {1} --show-upgraded upgrade".format(yes, noauth)
        perform.execute(command, root=True)
    else:
        print('No upgradeable packages. Did you run "wajig update" first?')
