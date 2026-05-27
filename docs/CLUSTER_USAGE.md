# Galileo100 cluster usage manual
## 0) Create & manage token classic GitHub
Go to GitHub and create a token of type classic with the necessary privileges needed to handle repository cloning and save it in a secure location on you local machine.
## 1) Create new authentication certificate for the current session
```bash
step ssh login '<USER_MAIL>' --provisioner cineca-hpc
```
Substitute USER_MAIL with the email of your CINECA account, then a CINECA login webpage will pop-up, login using you credentials and the OPT code.
## 2) Access Galileo100

```bash
ssh <USERNAME>@login.g100.cineca.it
```
```bash
ssh-keygen -R login.g100.cineca.it
```
Substitute USERNAME with the username associate with your CINECA account, than a confirmation is printed into terminal, accept it, and you are logged into the Galileo100 cluster.
To check how many computational credits you currently have do:
```bash
saldo -b
```
## 3) Clone repository into cluster using token
```bash
git clone https://github.com/DomDegi/DegiorgioPelorosso.git
```
Login to GitHub using your email and the token as your password.
## 5) Submit work
```bash
sbatch run_job.slurm
```
To see SLURM queue do:
```bash
squeue -u $USER
```
To see files produced do:
```bash
cat <FILE_NAME>
```
To logout from the cluster do:
```bash
exit
```