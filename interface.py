import tkinter as tk
from tkinter import ttk
import os

# IMPORTER LA LOGIQUE DE L'AGENT
from agent import get_agent_response

class IsmailaChatbot:
    def __init__(self, master):
        self.master = master
        master.title("ISMaiLa Agent")
        master.geometry("500x600")
        master.configure(bg="#ffffff")
        master.resizable(True, True)

        # --- Cadre principal pour les messages (Canvas avec Scrollbar) ---
        self.messages_canvas_frame = tk.Frame(master, bg='white', bd=2, relief="groove")
        self.messages_canvas_frame.pack(pady=10, padx=10, fill="both", expand=True)

        self.canvas = tk.Canvas(self.messages_canvas_frame, bg='white', highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self.messages_canvas_frame, orient="vertical", command=self.canvas.yview)
        
        self.scrollable_frame = tk.Frame(self.canvas, bg='white')

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind('<Configure>', self.on_canvas_configure)

        # --- Cadre pour l'entrée utilisateur ---
        self.input_frame = tk.Frame(master, bg="#c1bebe")
        self.input_frame.pack(pady=10, padx=10, fill="x", side="bottom")

        # Champ de saisie
        self.user_input = tk.Entry(self.input_frame, font=('Arial', 10), bd=1, relief="solid", highlightbackground="#ccc", highlightthickness=1)
        self.user_input.pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 10))
        self.user_input.bind("<Return>", self.send_message_event)

        # Bouton Envoyer
        self.send_button = tk.Button(self.input_frame, text="Envoyer", command=self.send_message, font=('Arial', 10, 'bold'), bg='#007bff', fg='white', activebackground='#0056b3', activeforeground='white', relief="raised", bd=2)
        self.send_button.pack(side=tk.RIGHT)

        # Message de bienvenue initial
        self.add_message("Bonjour ! Je suis ISMAILA, votre assistant universitaire. Comment puis-je vous aider aujourd'hui ?", "bot")

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw"), width=event.width)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # --- Fonction pour ajouter un message (bulle) au chat ---
    def add_message(self, text, sender):
        message_bubble_frame = tk.Frame(self.scrollable_frame, bd=0, bg='white')

        # Styles des bulles
        current_canvas_width = self.canvas.winfo_width() # Obtenir la largeur actuelle du canvas
        
        # Initialisation de wrap_length_val pour s'assurer qu'elle existe toujours
        wrap_length_val = current_canvas_width * 0.7 # Valeur par défaut si non définie

        if sender == "user":
            bg_color = "#C76F0B" # background l'utilisateur
            fg_color = "#FEFEFE" # Text l'utilisateur
            align_anchor = "e" # 'e' pour East (droite)
            padx_value = (50, 5) # Marge à gauche pour la bulle utilisateur
            # Calcul du wraplength: largeur du canvas - marge latérale - padding interne total
            # padx_value[0] = marge gauche (50), padx_value[1] = marge droite (5)
            # On retire l'espace non utilisé de la largeur du canvas pour le texte
            wrap_length_val = current_canvas_width - padx_value[0] - padx_value[1] - 20 # Ajustement de 20 pour la sûreté
        else: # bot
            bg_color = "#EF9C2F" # background pour le bot
            fg_color = "#FFFFFF" # Text pour le bot
            align_anchor = "w" # 'w' pour West (gauche)
            padx_value = (5, 50) # Marge à droite pour la bulle bot
            # Calcul similaire pour le bot
            wrap_length_val = current_canvas_width - padx_value[0] - padx_value[1] - 20 # Ajustement de 20 pour la sûreté

        # Si le calcul donne une valeur non valide, mettez un minimum
        if wrap_length_val <= 0:
            wrap_length_val = 200 # Minimum raisonnable pour que le texte soit visible

        message_label = tk.Label(
            message_bubble_frame,
            text=text,
            bg=bg_color,
            fg=fg_color,
            font=('Arial', 10),
            wraplength=wrap_length_val, # UTILISATION DU CALCUL DYNAMIQUE
            justify=tk.LEFT if sender == "bot" else tk.RIGHT,
            padx=10, # Padding interne du texte
            pady=7,
            relief="flat",
            anchor=align_anchor
        )
        message_label.pack(side=tk.TOP, anchor=align_anchor, fill="x", padx=0, pady=0, expand=True)

        # Positionne la bulle complète (frame) dans le scrollable_frame
        message_bubble_frame.pack(side=tk.TOP, fill="x", anchor=align_anchor, pady=(2,2), padx=padx_value) # ICI padx_value est enfin définie !

        # Mettre à jour le scrollregion et défiler vers le bas
        self.canvas.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        self.canvas.yview_moveto(1.0)


    def send_message_event(self, event=None):
        self.send_message()

    def send_message(self):
        user_question = self.user_input.get()
        if user_question.strip() == "":
            return

        self.add_message(user_question, "user")
        self.user_input.delete(0, tk.END)

        bot_answer = get_agent_response(user_question)
        self.add_message(bot_answer, "bot")

# --- Initialisation de l'Application Tkinter ---
if __name__ == "__main__":
    root = tk.Tk()
    app = IsmailaChatbot(root)
    root.mainloop()