import torch
import os

from tqdm import tqdm
from utils.utils import seed_everything
import numpy as np

import wandb




save_folder_path = '/home/xinda/codes/rxn_finetune/save/finetune_50k'
valid = True

os.makedirs(save_folder_path,exist_ok=True)
class Trainer(object):
    def __init__(self, task, cfg):
        wandb.init(project="RxnGPT_new_train3")
        self.task = task
        self.cfg = cfg

        self.accelerator = task.accelerator
        self.wandb = task.wandb
        self.logger = task.logger

        self.train_dataloader = task.train_dataloader
        self.valid_dataloader = task.valid_dataloader
        self.train_datasets = task.train_datasets
        self.valid_datasets = task.valid_datasets
        self.max_train_steps = task.max_train_steps

        self.model = task.model
        self.ema = task.ema

        self.accelerator = task.accelerator
        self.optimizer = task.optimizer
        self.lr_scheduler = task.lr_scheduler
        self.train_min_loss = 999
        self.valid_min_loss = 999
        super().__init__()

    def train(self):
        # Train!
        total_batch_size = self.cfg.SOLVER.TRAIN_BSZ * self.accelerator.num_processes * self.cfg.SOLVER.GRADIENT_ACC
        self.logger.info("***** Running training *****")
        self.logger.info(f"  Num examples = {len(self.train_datasets)} + {len(self.valid_datasets)}")
        self.logger.info(f"  Num Epochs = {self.cfg.SOLVER.MAX_EPOCHS}")
        self.logger.info(f"  Instantaneous batch size per device = {self.cfg.SOLVER.TRAIN_BSZ}")
        self.logger.info(f"  Total train batch size (w. parallel, distributed & accumulation) = {total_batch_size}")
        self.logger.info(f"  Gradient Accumulation steps = {self.cfg.SOLVER.GRADIENT_ACC}")
        self.logger.info(f"  Total optimization steps = {self.max_train_steps}")
        # Only show the progress bar once on each machine.
        progress_bar = tqdm(range(self.max_train_steps), disable=not self.accelerator.is_local_main_process)

        for epoch in range(1, self.cfg.SOLVER.MAX_EPOCHS+1):
            seed_everything(self.cfg.seed + epoch)
            # train one epoch
            if True:
                self.train_epoch(
                    train_dataloader=self.train_dataloader,
                    gradient_accumulation_steps=self.cfg.SOLVER.GRADIENT_ACC,
                    accelerator=self.accelerator,
                    model=self.model,
                    optimizer=self.optimizer,
                    lr_scheduler=self.lr_scheduler,
                    progress_bar=progress_bar,
                    args=self.cfg.SOLVER,
                    epoch=epoch
                )
            # eval
            if self.ema is not None:
                ema_model = self.ema.ema
                model = ema_model
            else:
                ema_model = None
                model = self.model
            if valid:
                self.valid(epoch, self.accelerator, model, self.valid_dataloader, args=self.cfg.SOLVER)
            torch.save(model.state_dict(),'{}/train_epoch_{}.pth'.format(save_folder_path,int(epoch)))

            # if self.cfg.MODEL.PEFT.LoRA:
            #     # folder_path_i = '{}/train_epoch_{}'.format(save_folder_path,int(epoch))
            #     # os.makedirs(folder_path_i, exist_ok=True)
            #     # model.save_pretrained(folder_path_i)
            #     self.save_model(model, ema_model, epoch=epoch)
            # else:
            #     torch.save(model.state_dict(),'{}/train_epoch_{}.pth'.format(save_folder_path,int(epoch)))

            # save
            # self.accelerator.wait_for_everyone()
            # if epoch % self.cfg.SOLVER.SAVE_STEP == 0:
            #     # self.model.save_pretrained(os.path.join('save', self.cfg.save))
            #     self.save_model(model, ema_model, epoch=epoch)
            
            # self.save_model(model, ema_model, epoch=epoch)
        self.logger.info(f"  =====================================================================================")
        self.logger.info(f"  train finish!  ")
        self.logger.info(f"  =====================================================================================")

    def save_model(self, model, ema_model, epoch=None):
        unwrapped_model = self.accelerator.unwrap_model(model)
        save_name = self.cfg.task_name
        if epoch != None:
            save_file_name = f'{save_name}_{epoch}.pt'
        else:
            save_file_name = f'{save_name}_best.pt'

        model_dict = {'model': unwrapped_model.state_dict()}
        if ema_model is not None:
            model_dict['ema_model'] = self.accelerator.unwrap_model(ema_model).state_dict()

        # torch.save(model_dict, os.path.join('save', self.cfg.save, save_file_name))

    def train_epoch(self, train_dataloader, gradient_accumulation_steps, accelerator,
                    model, optimizer, lr_scheduler, progress_bar, args,epoch):
        model.train()

        loss_values = []
        for step, item in enumerate(train_dataloader):
            self.train_step(step, gradient_accumulation_steps, accelerator, model, train_dataloader, item, optimizer,
                       lr_scheduler, progress_bar, loss_values, args)
            if step%1000==0 and step!=0:
                torch.save(model.state_dict(),'{}/train_epoch_{}_step_{}.pth'.format(save_folder_path,int(epoch),int(step)))
            # if step%20000==0 and step!=0:
            #     torch.save(model.state_dict(),'{}/train_epoch_{}_step_{}.pth'.format(save_folder_path,int(epoch),int(step)))

    def train_step(self, step, gradient_accumulation_steps, accelerator, model, train_dataloader,
                   item, optimizer, lr_scheduler, progress_bar, loss_values, args):
        out = model(**item)

        loss = out['loss']
        loss = loss / gradient_accumulation_steps
        loss_values.append(loss.item())
        accelerator.backward(loss)
        # clip gradient
        if args.CLIP_GRAD is not False:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=args.CLIP_GRAD)

        wandb.log({"loss_per_train_step": loss.clone().cpu().item()}) ###

        if step % gradient_accumulation_steps == 0 or step == len(train_dataloader) - 1:
            optimizer.step()
            lr_scheduler.step()
            optimizer.zero_grad()

            if self.ema is not None:
                self.ema.update(model)

            total_loss_value = sum(loss_values)

            progress_bar.set_description(
                f'loss {total_loss_value:.4f}, lr:{optimizer.param_groups[0]["lr"]:.7f} ',
                refresh=False)
            progress_bar.update(1)

            if 'param_groups' in optimizer.state_dict():
                current_lr = optimizer.state_dict()['param_groups'][0]['lr']
            else:
                current_lr = optimizer.state_dict()['base_optimizer_state']['param_groups'][0]['lr']

            if accelerator.is_main_process and not self.cfg.debug:
                report = {'learning_rate:': current_lr}
                train_log = {'train_'+k: v for k, v in out.items()}
                report.update({k: float(v) for k, v in train_log.items() if len(v.shape) == 0})
                wandb.log(report)
            loss_values.clear()


    def validation_log_dict(self, outputs):
        ks = outputs[0].keys()
        log_dict = {}
        for k in ks:
            temp = []
            for step_output in outputs:
                if not torch.is_tensor(step_output[k]):
                    temp.append(torch.tensor(step_output[k]))
                else:
                    temp.append(step_output[k])
            if temp == []:
                continue
            if len(temp[0].shape) > 0:
                log_dict[k] = torch.cat(temp).mean()
            elif len(temp[0].shape) == 0:
                log_dict[k] = torch.tensor(temp).mean()
        return log_dict

    def valid(self, epoch, accelerator, model, eval_dataloader, args):
            model.eval()
            with torch.no_grad():
                loss_list = []
                outputs = []
                for step, item in enumerate(eval_dataloader):
                    loss = model(**item)['loss']
                    outputs.append({'loss':  loss})
                    loss_list.append(loss.clone().cpu().item())

                    wandb.log({"loss_per_valid_step": loss.clone().cpu().item()}) ###
                log_dict = self.validation_log_dict(outputs)

            valid_loss_mean = np.mean(loss_list)
            if valid_loss_mean < self.valid_min_loss:
                self.valid_min_loss = valid_loss_mean
                # self.save_model(model, self.ema.ema, epoch=epoch)


                # if self.cfg.MODEL.PEFT.LoRA:
                #     # folder_path_i = '{}/valid_epoch_{}'.format(save_folder_path,int(epoch))
                #     # os.makedirs(folder_path_i, exist_ok=True)
                #     # model.save_pretrained(folder_path_i)
                #     self.save_model(model, self.ema.ema, epoch=epoch)
                # else:
                #     torch.save(model.state_dict(),'{}/valid_epoch_{}.pth'.format(save_folder_path,int(epoch)))

        
            report = {'valid_' + k: float(v) for k, v in log_dict.items()}
            report['epoch'] = epoch
            self.logger.info(report)
            if accelerator.is_main_process and not self.cfg.debug:
                wandb.log(report)

    # def valid(self, epoch, accelerator, model, eval_dataloader, args,step):
    #     model.eval()
    #     with torch.no_grad():
    #         loss_list = []
    #         outputs = []
    #         for step, item in enumerate(eval_dataloader):
    #             loss = model(**item)['loss']
    #             outputs.append({'loss':  loss})
    #             loss_list.append(loss.clone().cpu().item())

    #             wandb.log({"loss_per_valid_step": loss.clone().cpu().item()}) ###
    #         log_dict = self.validation_log_dict(outputs)

    #     valid_loss_mean = np.mean(loss_list)
    #     if valid_loss_mean < self.valid_min_loss:
    #         self.valid_min_loss = valid_loss_mean
    #         # self.save_model(model, self.ema.ema, epoch=epoch)
    #         if self.cfg.MODEL.PEFT.LoRA:
    #             # folder_path_i = '{}/valid_epoch_{}'.format(save_folder_path,int(epoch))
    #             # os.makedirs(folder_path_i, exist_ok=True)
    #             # model.save_pretrained(folder_path_i)
    #             self.save_model(model, self.ema.ema, epoch=epoch)
    #         else:
    #             torch.save(model.state_dict(),'{}/valid_epoch_{}_step_{}.pth'.format(save_folder_path,int(epoch),int(step)))

     
    #     report = {'valid_' + k: float(v) for k, v in log_dict.items()}
    #     report['epoch'] = epoch
    #     self.logger.info(report)
    #     if accelerator.is_main_process and not self.cfg.debug:
    #         wandb.log(report)
