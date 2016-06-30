#!/usr/bin/env python
###################################################################
#
#   This is a simple tool for spinning up instances in AWS
#       - Please place your AWS key credentials in a boto config file in the default location of your choosing. Default searched locations in Linux/OSX are ~/.boto or /etc/boto.cfg.
#          Windows is in %USERPROFILE%\boto.cfg IE "C:\Users\Me\boto.cfg" or %USERPROFILE%\.boto. Be aware that explorer will not easily rename files that start with ".". 
#          (this script has been tested on Ubuntu 14.4, Windows 7/10, and OSX 10.11)
#           The process is outlined here:   http://boto.cloudhackers.com/en/latest/boto_config_tut.html
#
#       - There is deconstruction available via the term flag allowing termination of instances when given the instance id desired.
#             !!!Beware, termination means the loss/destruction of all local data on an instance!!!
#                   (You can get a list of all running/stopped instances by using -term with any, even an invalid id and using '-list')
#
#   NOTES:
#
#       - This is a script written using Python 2.7 from the default install dir - Please note the initial shebang, 
#           and the path variables may need to be adjusted to suit your installation/OS!!!
#        
#       - Requires the boto python module to be installed. It can be installed via "pip install boto"
#               http://boto.cloudhackers.com/en/latest/getting_started.html
#
#       - If logging in via ssh is desired, you will need to use a public/private keypair from AWS. If you are not coming from a 10.0.0.0/8 add your public ip address below 
#               ( If you need to find your external ip google "what is my IP" )
#               (If you don't have an existing keypair in an AWS security group, it will be created for you in createInstance()
#   TODO:
#       - Output errors to log
#       - Output to email, possibly a web hook
#       - Retrieve AWS credentials from a secure store  ( may also be handled outside this script with configuration management such as puppet/hiera)
#       - Re-factor code out into more reasonable/smaller defs for readability, maintainability, and modularity  
#       - Add security group rule evaluation and revocation. 
#       - Expand flexibility of security rule implementation 
#       
#
#
###################################################################


import time
import os
import sys
import collections
import argparse

try:
    import boto.ec2
    
except ImportError:
    print "Error: The boto module is either not installed, failed to load, or has an improper path\nPlease see:\n    http://boto.cloudhackers.com/en/latest/getting_started.html"
    sys.exit(2)
    
    
#############################################################################################################
# Configureation parameters                                                                                 # 
#                                                                                                           # 
#############################################################################################################

#   You can replace the  security group, keypair names if desired, and keypair storage location. (Be aware of OS pathing!)
my_security_group_name = 'Flask_Tests'
my_keypair_name = 'Flask_key'

#  An array for any ip addresses you want to have SSH access via a newly created security group to the instance
#   you must add the address to the following array as a string. 
#   The default example assumption is made that you are in a 10.*.*.* ip range and it is included.
#   This will NOT affect groups that have already been created
additional_ssh_ips = [ "10.0.0.0/8", ]

#############################################################################################################
# End Configureation parameters                                                                             # 
#                                                                                                           # 
#############################################################################################################


my_key_save_dir    = os.path.abspath(os.path.dirname(sys.argv[0])) + '/' + 'key'
my_keypair_file    = my_key_save_dir + '/' +  my_keypair_name + '.pem'
my_user_data       = os.path.abspath(os.path.dirname(sys.argv[0])) + "/user_data"
my_aws_region_list = ['us-east-1', 'us-west-1', 'us-west-2']

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

        
def userPrompt(question, answers):
    # This user prompt will be reusable for creating or terminating instances
    # Setting up a switch to let us know when we have an acceptable user answer
    acceptable = False
    
    while not acceptable:
        print(question + "specify '%s' or '%s'") % answers
        answer = raw_input()
        if answer.lower() == answers[0].lower() or answers[0].lower():
            print('You answered: %s') % answer
            acceptable = True
    return answer


def createInstance():
    # TODO: have function accept reservation values as variables
    # Creating EC2 instance in us-east-1, where it is cheap
    
    if args.force:
        pass
        
    elif not args.force:
        user_answer = userPrompt("\nAre you sure you want to create this instance?! Instances can cost $!!!\n", ('y', 'n'))
        if user_answer == 'y':
            pass
        else:
            print "You must say yes to creating the instance, throw the '-f' flag to force, or not create an instance"
            sys.exit(2)
    
    
    
    try:
        conn = boto.ec2.connect_to_region(str(args.awsregion),
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
                        if not os.path.exists(my_key_save_dir):
                            os.makedirs(my_key_save_dir)
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
            # Setting up our security group
            groups = [g for g in conn.get_all_security_groups() if g.name == my_security_group_name]
            group = groups[0] if groups else None
            if not group:
                print "Creating group '%s'..."%(my_security_group_name,)
                group = conn.create_security_group(my_security_group_name, "A group for %s"%(my_security_group_name,))
                for rule in flask_test_rules:
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
            args.ami,
            key_name=my_keypair_name,
            instance_type=args.instancetype,
            user_data=readFileToVar(my_user_data),
            security_groups=[my_security_group_name]
            )

        return reservation  
        
    except boto.exception.BotoServerError:
        print "Instance creation error - Check that regions, AMIs, and machine types are proper."
        sys.exit(2)
        
        
def tester(test_type):
    # Make an instance
    if test_type == 'make':
        new_instance = createInstance()
        print new_instance.instances[0].id
        
    # Test an existing instance
    instance_id_test = ''
    inst_stuff = boto.ec2.get_only_instances(instance_ids=[instance_id_test])



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
            

def terminateInstance(term_instance_id):
    # Checking for, then terminating matching instances
    
    # Keeping track of whether or not we found a matching instance, and if prompted, the outcome
    found_instance_id = False
    delete_yes      = False
    # If we're listing found instances, stick the ids here
    instance_id_list = list()
    
    try:
            # Setup AWS connection using our given region, access_key_id and secret_access_key
        conn = boto.ec2.connect_to_region(str(args.awsregion),
                                            aws_access_key_id = access_key_id,
                                            aws_secret_access_key = secret_access_key)            
        
        reservations = conn.get_all_reservations()
        
        # Comb through all our reservations in the given region
        for r in reservations:
            for i in r.instances:
                # Did we ask for an instance list? If the instances aren't terminated store it in a list
                if args.listinstances and not i.state == "terminated":
                    instance_id_list.append(i.id)

                # We are only acting on instances matching the given instance_id if it is 'running' or 'stopped'                    
                # (Already terminated instances don't require our attention)
                if (i.id == term_instance_id) and (i.state == "running" or i.state == "stopped"):
                        
                    # Setting our var so we get notice of its existence    
                    found_instance_id = True
                    
                    # Are we forcing deletion? Terminate
                    if args.force:
                        conn.terminate_instances(instance_ids=[term_instance_id])
                        # Setting our var so we know the outcome
                        delete_yes = True
                    
                    # We aren't forcing deletes? Ask the user permission
                    elif not args.force:
                        prompt_answer = userPrompt("\nAre you sure you want to terminate this instance?! ALL DATA WILL BE LOST FROM THAT INSTANCE!!!\n", ('y', 'n'))

                        # Our user confirmed termination? Terminate
                        if prompt_answer == 'y':
                            conn.terminate_instances(instance_ids=[term_instance_id])
                            # Setting our var so we know the outcome
                            delete_yes = True
                            
                        # Our user didn't confirm termination, move on    
                        else:
                            continue
                
                # If we found our instance but it's already terminated there's no need to act on it.
                elif (i.id == term_instance_id) and i.state == "terminated":
                    print "Instance %s is already terminated, nothing to act on" % term_instance_id
                    sys.exit(0)
                    
                else:
                    continue
        
        # If we asked for a list of the instances, print it here.
        if len(instance_id_list) > 0:
            print "\nList of instances found:\n%s" % instance_id_list
            
    except boto.exception.BotoServerError:
        print "Instance termination error - Check that regions, keys, and provided instance ids are correct."
        sys.exit(2)     

    # If our instance id exists and we deleted it tell us
    if found_instance_id and delete_yes:
        print "Matching instance was found and terminated"
        sys.exit(0)
    
    # If we found our instance id but we didn't delete it tell us
    elif found_instance_id and not delete_yes:
        print "Matching instance found but not terminated"
        sys.exit(0)
        
    # We didn't find our instance running or stopped, so let us know    
    else:
        print "No running or stopped instances with given id found"
        sys.exit(2)
    
if __name__=="__main__":            


    try:
        #   Initialize arg parser
        parser = argparse.ArgumentParser(description="This tool reads json data to calculate percentile points.")

        #   Setting up valid CLI args
        # The force flag can be used to bypass any user prompts - !!!Beware ultimate power!!!
        parser.add_argument("-f", "--force",
                        help="Forcing the command to run without user prompts",
                        action="store_true", default=False)
                        
        # In case a user doesn't have access to the AWS console and lost the Instance ID for an instance they
        #    want to terminate, they can use this in concert with '-term'. (A *valid* instance id is not necessary to see the list!)
        parser.add_argument("-list", "--listinstances",
                        help="Used in conjunction with '-term' to allow users to see what instance ids are available. (A valid instance id is not necessary for this)",
                        action="store_true", default=False)                        
                        
                        
        #  Breaking out the user data opens up this launch script to configure launched instances in multiple configurations.
        parser.add_argument("-ud", "--userdata",
                        help="Specifies a user data file instead of the default",
                        action="store", default=False)

                        
        #  Breaking out the key store dir allows us to place new keys in a shared store, etc.
        parser.add_argument("-kd", "--keydir",
                        help="Specifies a key directory instead of the default",
                        action="store", default=False)
                        
        #  Breaking out the security group name to open options
        parser.add_argument("-sg", "--securitygroup",
                        help="Specifies a security group name beyond the default",
                        action="store", default=False)

        #  Breaking out the key pair name to open options
        parser.add_argument("-kp", "--keypair",
                        help="Specifies a key pair name beyond the default",
                        action="store", default=False)
                        
        #  Breaking out aws region to open options
        parser.add_argument("-ar", "--awsregion",
                        help="Specifies the AWS region you want to create an instance in. Default: 'us-east-1'  Ensure your AMI is available for that region!",
                        action="store", default='us-east-1')

        #  Breaking out the ami name to open options (To ensure compatability another puppet config may be necessary)
        parser.add_argument("-am", "--ami",
                        help="Specifies AMI you want to use create an instance. Default: 'ami-fce3c696'  Ensure your AMI is available for that region!",
                        action="store", default='ami-fce3c696')                     
                        
        #  Breaking out the instance type we'll create, to open options
        parser.add_argument("-it", "--instancetype",
                        help="Specifies the instance type you want to spin up. Default: 't2.micro'  Ensure your instance type is available for that region!",
                        action="store", default='t2.micro')                         
                        
        #  Setting up deconstruction. This is also available in the AWS console. (Please see AWS documentation)
        parser.add_argument("-term", "--terminate",
                        help="When terminating, not creating an instance specify instance id, ie; 'i-00000000'",
                        action="store")

                        
        # Parse arguments
        args = parser.parse_args()                        
                        
        if args.userdata and not os.path.isfile(args.userdata):
            parser.error("No user data file specified to act on, or bad path.")
            sys.exit(1)
            
        elif args.keydir and not os.path.isdir(args.keydir):
            parser.error("No key dir specified to act on, or bad path.")
            sys.exit(1)

        elif args.securitygroup and not isinstance(args.securitygroup, str):
            parser.error("No security group specified. Don't use the -sg flag if you want to use the default.")
            sys.exit(1)

        elif args.keypair and not isinstance(args.keypair, str):
            parser.error("No key pair name specified. Don't use the -kp flag if you want to use the default.")
            sys.exit(1)            

        elif args.awsregion and not (isinstance(args.awsregion, str) and args.awsregion in my_aws_region_list):
            parser.error("Invalid AWS Region specified. Current options:%s" % my_aws_region_list)
            sys.exit(1)
            
        # NOTE: AMIs and Instances can have a built-in validation scheme like the regions above, following the same setup
        #         or it coud be broken out into an ini.
        elif args.ami and not isinstance(args.ami, str):
            parser.error("Invalid AMI specified.")
            sys.exit(1)

        elif args.instancetype and not isinstance(args.instancetype, str):
            parser.error("Invalid Instance type specified.")
            sys.exit(1)         
            
        else:
            try:
                # Changing global vars if custom data is called
                if args.userdata:
                    my_user_data = str(args.userdata)
                
                if args.keydir:
                    my_key_save_dir = str(args.keydir)
                    
                if args.securitygroup:
                    my_security_group_name = str(args.securitygroup)

                if args.keypair:
                    my_keypair_name = str(args.keypair)
                
                if not args.terminate:
                    new_instance = createInstance()
            
                    # Use instance id and watch its status.         
                    instanceCreationStatus(new_instance.instances[0], "update", "state", "running")

                else:
                    # If args.terminate is populated, we look to terminate the given instance
                    terminateInstance(args.terminate)
                    
                    
            except Exception as e:
                print "Error running options: %s" %  e
                sys.exit(1)    
                        
    except Exception as e:
        print "Error in argparsing: %s" %  e
        sys.exit(1)
