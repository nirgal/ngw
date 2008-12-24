#!/usr/bin/env python
# -*- coding: utf-8 -*-

GPG_HOME = "/var/lib/ngw/"

import subprocess

# TODO: use --edit-key deluid to keep only one uid per key ?

def subprocess_run(*args):
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    out, err = process.communicate()
    return process.returncode, out, err


def parse_pgp_listkey(output):
    keyring = {}
    for line in output.split('\n'):
        #print repr(line)
        if line.startswith('pub'):
            line = line[6:]
            algo_id, dt = line.split(" ", 1)
            algo, id = algo_id.split("/", 1)
            #print algo, id, dt
            keyring[id] = { 'uids': [], 'algo': algo, 'date': dt }
        elif line.startswith('uid'):
            p1 = line.find('<')
            p2 = line.find('>')
            #print p1,p2, len(line)
            if p1==-1 or p2==-1 or p2!=len(line)-1:
                print "Error parsing uid line in gpg --list-keys"
                continue
            mail = line[p1+1:p2]
            name = line[4:p1].strip()
            #print "*", mail, "*", name, "*", id
            keyring[id]['uids'].append((name, mail))
    return keyring

def is_email_secure(mail_address):
    if mail_address.startswith("-"):
        return False # Possible hack attempt
    ret, out, err = subprocess_run("gpg", "--homedir", GPG_HOME, "--list-keys", mail_address)
    if ret:
        return False # gpg error
    keyring_1 = parse_pgp_listkey(out)
    return len(keyring_1)>0
    
def loadkeyring():
    ret, out, err = subprocess_run("gpg", "--homedir", GPG_HOME, "--list-keys")
    if ret:
        print err
        print "gpg failed."
    return parse_pgp_listkey(out)


if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    (options, args) = parser.parse_args()
    print loadkeyring()
