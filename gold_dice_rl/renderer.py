import matplotlib.pyplot as plt


def _extract(history, key, default=0):
    return [row.get(key, default) for row in history]


def plot_episode(history, save_path=None, show=True):

    if not history:
        print("No history to plot. Use GoldDiceEnv(track_history=True).")
        return

    turns = _extract(history, "turn")

    gold = _extract(history, "gold")
    points = _extract(history, "points")

    shields = _extract(history, "shields")
    storms = _extract(history, "storm", False)
    storm_blocked = _extract(history, "storm_blocked", False)

    num_dice = _extract(history, "num_dice")
    dice_bonus = _extract(history, "dice_bonus")

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)

    # Gold and points
    axes[0].plot(turns, gold, marker="o", label="Gold")
    axes[0].plot(turns, points, marker="o", label="Points")
    axes[0].set_ylabel("Amount")
    axes[0].set_title("Gold and points per turn")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Shields and storms
    axes[1].plot(turns, shields, marker="o", label="Shields")

    storm_turns = [t for t, s in zip(turns, storms) if s]
    blocked_turns = [t for t, b in zip(turns, storm_blocked) if b]

    if storm_turns:
        axes[1].scatter(
            storm_turns,
            [1] * len(storm_turns),
            marker="x",
            s=90,
            label="Storm",
        )

    if blocked_turns:
        axes[1].scatter(
            blocked_turns,
            [1] * len(blocked_turns),
            marker="s",
            s=60,
            label="Storm blocked",
        )

    axes[1].set_ylabel("Count / event")
    axes[1].set_title("Shields and storms")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # Dice and upgrades
    axes[2].plot(turns, num_dice, marker="o", label="Number of dice")
    axes[2].plot(turns, dice_bonus, marker="o", label="Dice bonus / upgrades")
    axes[2].set_xlabel("Turn")
    axes[2].set_ylabel("Count")
    axes[2].set_title("Dice count and upgrades")
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)

    axes[2].set_xticks(turns)

    plt.tight_layout()

    if save_path is not None:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved plot to {save_path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_gold_points(history, save_path=None, show=True):

    if not history:
        print("No history to plot. Use GoldDiceEnv(track_history=True).")
        return

    turns = _extract(history, "turn")
    gold = _extract(history, "gold")
    points = _extract(history, "points")

    plt.figure(figsize=(10, 4))
    plt.plot(turns, gold, marker="o", label="Gold")
    plt.plot(turns, points, marker="o", label="Points")
    plt.xlabel("Turn")
    plt.ylabel("Amount")
    plt.title("Gold and points per turn")
    plt.xticks(turns)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    if save_path is not None:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved plot to {save_path}")

    if show:
        plt.show()
    else:
        plt.close()


def plot_game_state(history, save_path=None, show=True):
    plot_episode(history, save_path=save_path, show=show)