# flask_launch_instance

    This document is an outline for the deployment of a Flask web app and server.
      Components:
          - A Python boto script to launch an EC2 instance and return relevant instance data
                (Launch.py)
               
          - A User Data file to be passed to AWS during the spawning of an instance that intially installs Puppet and git
                (user_data)
               
          - A boto.cfg file to store AWS credentials.
              Please place your AWS key credentials in a boto config file in the default location of your choosing. Default searched locations in Linux/OSX are ~/.boto or /etc/boto.cfg.
                Windows is in %USERPROFILE%\boto.cfg IE "C:\Users\Me\boto.cfg" or %USERPROFILE%\.boto. Be aware that explorer will not easily rename files that start with ".".
               (this script has been tested on Ubuntu 14.04, Windows 7/10, and OSX 10.11)
                The process is outlined here:   http://boto.cloudhackers.com/en/latest/boto_config_tut.html
         
          - A set of Puppet modules/manifests/files hosted on Github that is used for managing our packages/installs and setup the server
         
          - An app.py Flask app file hosted on Github that can be updated as needed by production.
         
         
      Requirements:
          - An internet connection
         
          - The ability to run a git clone or checkout of git repositories via https
         
          - AWS login credentials capable of creating IAM roles, security groups, and EC2 instances
         
          - Python 2.7
            - The boto module (If installing via pip, install pip then 'pip install boto')
             
           
      boto.cfg construction:

        The boto.cfg or .boto  file is straight forward and is constructed as such ( see above notes for placement details):
       
        [credentials]
        aws_access_key_id     = <YOUR_ACCESS_KEYE_HERE>
        aws_secret_access_key =    <YOUR_SECRET_ACCESS_KEY_HERE>


      Summary of Events:
     
      - User pulls down the deployment repository from github
           (Files are run out of the directory the repository has been pulled down from, but variables can be changed in the script if desired)
          
      - User populates the boto.cfg file with their own AWS credentials

      - User Installs necessary packages, Python 2.7, and boto
     
      - User runs Launch.py from the command line and receives pertinent Instance data. (ID, Private IP, External Public IP)
     
      - Launch.py creates a security group, a keypair if needed and opens desired networks ports for communication
     
      - Launch.py launches an EC2 t2.micro instance with user_data included to AWS setting up our Ubuntu 14.04 AMI in US-EAST-1
     
      - The user_data pre-loads the instance with Puppet and Git, and pulls down our repository to configure the server
          ( https://github.com/spotts-moz/flask_config )
     
      - The instance uses puppet to install and run Nginx, Uwsgi, Git, and deploy our flask app(via Git) then creates a cron job
          that runs puppet apply every hour enabling vcsrepo to update to the latest version of our flask app and puppet configs in master.
          The app and puppet configs stay current if the instance should remain persistent rather than being re-deployed after every change
          (Good for small team testing without a CI/CD framework)

     
     
      TODO:
     
      - Outside of the scope of this exercise more focus would be paid to security. (using virtualenv, key pairs, secret stores, identity checking, etc)
      - The Launch script could be broken out into more functions and parts to allow more flexible changes.
      - Variables from launch.py could be broken out into an ini, or be parsed from the command line as arguments.
