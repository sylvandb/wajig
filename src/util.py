#!/usr/bin/env python
#
# WAJIG - Debian Command Line System Administrator
#
# Copyright (c) Graham.Williams@togaware.com
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version. See the file LICENSE.
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

"Contains miscellaneous utilities."

import os
import sys

import apt

pause = False
interactive = False


def requires_no_args(command, args, test=False):
    if len(args) > 1:
        if not test:
            message = "no further arguments"
            print "WaJIG Error: " + command.upper() + " requires " + message
            finishup(1)
        return False
    return True


def requires_one_arg(command, args, message=False):
    if len(args) != 2:
        if message:  # checks if this is a unit test
            print "WaJIG Error: " + command.upper() + " requires " + message
            finishup(1)
        return False
    return True


def requires_two_args(command, args, message=False):
    if len(args) != 3:
        if message:  # checks if this is a unit test
            print "WaJIG Error: " + command.upper() + " requires " + message
            finishup(1)
        return False
    return True


def requires_opt_arg(command, args, message=False):
    if len(args) > 2:
        if message:  # checks if this is a unit test
            print "WaJIG Error: " + command.upper() +\
                  " has one optional arg: " + message
            finishup(1)
        return False
    return True


def requires_args(command, args, required=False):
    if len(args) == 1:
        if required:  # checks if this is a unit test
            print "WaJIG Error: {0} requires {1}".\
                   format(command.upper(), required)
            finishup(1)
        return False
    return True


def requires_package(package, path, test=False):
    if not os.path.exists(path):
        if not test:
            print 'This command depends on "' + package + '" being installed.'
            finishup(1)
        return False
    return True


def package_exists(package, test=False):
    cache = apt.Cache()
    try:
        cache[package]
        return True
    except KeyError, e:
        if not test:
            print e[0]
            finishup(1)


def upgradable(distupgrade=False):
    "Checks if the system is upgradable."
    cache = apt.Cache()
    cache.upgrade(distupgrade)
    pkgs = [pkg.name for pkg in cache.get_changes()]
    return pkgs


def concat(args):
    result = str()
    for a in args:
        result += "'{0}' ".format(a)
    return result


def finishup(code=0):
    if pause:
        print "Press Enter to continue...",
        sys.stdin.readline()
    if not interactive:
        sys.exit(code)


def help_cmd(cmd):
    filename = "/usr/share/wajig/help/" + cmd
    try:
        with open(filename) as f:
            for line in f:
                print line[:-1]
    except:
        print "Command", cmd.upper(), "does not exist."
