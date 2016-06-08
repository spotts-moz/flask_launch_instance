#!/usr/bin/env python
###################################################################
#
#   This is a simple tool for spinning up instances in AWS
#       - Please place your AWS key credentials in a boto config file in the default location of your choosing. Default searched locations in Linux/OSX are ~/.boto or /etc/boto.cfg.
#          Windows is in %USERPROFILE%\boto.cfg IE "C:\Users\Me\boto.cfg" or %USERPROFILE%\.boto. Be aware that explorer will not easily rename files that start with ".". 
#          (this script has been tested on Ubuntu 14.4, Windows 7/10, and OSX 10.11)
#           The process is outlined here:   http://boto.cloudhackers.com/en/latest/boto_config_tut.html
#
#   NOTES:
#
#       - This is a script written using Python 2.7 from the default install dir - Please note the initial shebang, 
#           and the path variables may need to be adjusted to suit your installation/OS!!!
#        
#        - Requires the boto python module to be installed. It can be installed via "pip install boto"
#
#       - If logging in via ssh is desired, you will need to use a public/private keypair from AWS. If you are not coming from a 10.0.0.0/8 add your public ip address below 
#               ( If you need to find your external ip google "what is my IP" )
#               (If you don't have an existing keypair in an AWS security group, it will be created for you in createInstance()
#   TODO:
#       - Output errors to log
#       - Output to email, possibly a web hook
#       - Setup script to take variables through an ini file or the command line options.
#       - Create a more robust script that allows choosing of regions, with other AMIs etc
#       - Retrieve AWS credentials from a secure store  ( may also be handled outside this script with configuration management such as puppet/hiera)
#       - Re factor code out into more reasonable/smaller defs for readability, maintainability, and modularity  
#       - Add security group rule evaluation and revoke. 
#       - Expand flexibility of security rule implementation 
#       
#
#
###################################################################




import boto.ec2
import time
import os
import sys
import collections

#############################################################################################################
# Configureation parameters                                                                                 # 
#                                                                                                           # 
#############################################################################################################

# TODO make user_data able to be pulled from multiple sources
#       You can replace the user data, security group and keypair names if desired. (Be aware of OS pathing!)
my_user_data = "user_data" 
my_security_group_name = 'Flask_Tests'
my_keypair_name = 'Flask_keys'
my_key_save_dir = 'key'
my_keypair_file = my_key_save_dir + '/' +  my_keypair_name + '.pem'


#  An array for any ip addresses you want to have SSH access via a newly created security group to the instance
#   you must add the address to the following array as a string. 
#   The default example assumption is made that you are in a 10.*.*.* ip range and it is included.
#   This will NOT affect groups that have already been created
additional_ssh_ips = [ "10.0.0.0/8", ]

#############################################################################################################
# End Configureation parameters                                                                             # 
#                                                                                                           # 
#############################################################################################################

# TODO Access keys live and/or retrieved from somewhere other than boto.config possibly in secure data store
access_key_id     = boto.config.get_value('credentials', 'aws_access_key_id')
secret_access_key = boto.config.get_value('credentials', 'aws_secret_access_key')

# Setting up a security group namedtuple
SecurityGroupRule = collections.namedtuple("SecurityGroupRule", ["ip_protocol", "from_port", "to_port", "cidr_ip", "src_group_name"])


flask_test_rules = [
    SecurityGroupRule("tcp", "80", "80", "0.0.0.0/0", None),
    SecurityGroupRule("tcp", "443", "443", "0.0.0.0/0", None),
]

for i in additional_ssh_ips:
    flask_test_rules.append(SecurityGroupRule("tcp", "22", "22", i, None))

def readFileToVar(file):
    # This is a way to read in a file to become a variable, used in this case for user data
    try:
        if os.path.isfile(file):
            with open(file, "r") as f:
                user_data_file = f.read()
                
            return user_data_file
            
        else:
            print "Error, User Data file invalid."
            sys.exit(2)
    except:
        print "Error in readFileToVar"
        sys.exit(2)




def createInstance():
    # TODO: have function accept reservation values as variables
    # Creating EC2 instance in us-east-1, where it is cheap
    try:
        conn = boto.ec2.connect_to_region("us-east-1",
                                            aws_access_key_id = access_key_id,
                                            aws_secret_access_key = secret_access_key)
                                            
        try:
            
            # Check to see if specified keypair already exists.
            # If we get an InvalidKeyPair.NotFound error back from EC2,
            # it means that it doesn't exist and we need to create it.
            key = conn.get_all_key_pairs(keynames=[my_keypair_name])[0]
            
        except conn.ResponseError, e:
            if e.code == 'InvalidKeyPair.NotFound':
                print 'Creating new keypair: %s and saving in %s/' %(my_keypair_name, my_key_save_dir)
                # Keypair does not already exist, creating an SSH key to use when logging into instances.
                key = conn.create_key_pair(my_keypair_name)

                try:
                    if not os.path.isfile(my_keypair_file):
                                       
                        # AWS will store the public key but the private key is
                        # generated and returned and needs to be stored locally.
                        # We can't overwrite the file if one exists so saving the new file will be skipped
                        key.save(my_key_save_dir)
                
                except Exception as e:
                    print "Error creating key file" % e
                    sys.exit(2)
            else:
                raise
            
        except Exception as e:
            print "Error in key creation or saving: %s" % e
            sys.exit(2)
            
        try:
            groups = [g for g in conn.get_all_security_groups() if g.name == my_security_group_name]
            group = groups[0] if groups else None
            if not group:
                print "Creating group '%s'..."%(my_security_group_name,)
                group = conn.create_security_group(my_security_group_name, "A group for %s"%(my_security_group_name,))
                #current_rules = []
                for rule in flask_test_rules:
                    #current_rules.append(SecurityGroupRule(rule.ip_protocol, rule.from_port, rule.to_port, rule.grants[0].cidr_ip, None))
                    group.authorize(rule.ip_protocol,
                              rule.from_port,
                              rule.to_port,
                              rule.cidr_ip,
                              None)
        except Exception as e:
            print "Error in key creation or saving: %s" % e
            sys.exit(2)    

        # reservation will hold the return, which we can ask for .instances and see what instances it made.                                 
        reservation = conn.run_instances(
            'ami-fce3c696',
            key_name=my_keypair_name,
            instance_type='t2.micro',
            user_data=readFileToVar(my_user_data),
            security_groups=[my_security_group_name]
            )
            
        return reservation  
        
    except boto.exception.BotoServerError:
        print "Instance creation error"
        sys.exit(2)
        
        
def tester(test_type):
    # Make an instance
    if test_type == 'make':
        new_instance = createInstance()
        print new_instance.instances[0].id
        
    # Test an existing instance
    instance_id_test = ''
    inst_stuff = boto.ec2.get_only_instances(instance_ids=[instance_id_test])



#  Broken for now. In the aws init.py 'getattr' might be something I need.
def instanceCreationStatus(inst, update_method, attr_name, attr_value):
    while True:
        try:
            getattr(inst, update_method)()
            if getattr(inst, attr_name) == attr_value:
                # Tag isntance now that we are running 
                new_instance.instances[0].add_tag('Name', 'Flask-test-' + time.strftime("%X:%x:"))
                new_instance.instances[0].add_tag('Type', 'Flask-Hello-App-Server')
                
                print '\nInstance is Starting\n'
                print 'Created instance ID: %s\n' % new_instance.instances[0].id
                print 'Instance Private IP Address: %s\n' %  new_instance.instances[0].private_ip_address
                print 'Instance Public IP Address: %s\n' %  new_instance.instances[0].ip_address
                break
                
            else:
                time.sleep(2)
        except:
            print "Error while waiting, Retrying"
            time.sleep(15)
            
if __name__=="__main__":            
    new_instance = createInstance()
            
    # Use instance id and watch its status.         
    instanceCreationStatus(new_instance.instances[0], "update", "state", "running")             
    
    
    
 

