#include "VrgGameMode.h"

#include "VrgHud.h"
#include "VrgSceneActor.h"
#include "VrgSimActor.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpectatorPawn.h"

AVrgGameMode::AVrgGameMode()
{
	// A spectator pawn, not ADefaultPawn: the default one carries a visible
	// sphere mesh, and this pawn sits at the world origin -- which is exactly
	// where the vehicle starts, so it would hang a grey ball in the middle of
	// the first thing anyone looks at. The spectator has no mesh and still
	// free-flies if someone wants to leave the chase camera.
	DefaultPawnClass = ASpectatorPawn::StaticClass();
	PlayerControllerClass = APlayerController::StaticClass();

	// The standing disclaimer, on BOTH windows -- AVrgHud picks its own text
	// from -VrgMode. Set here rather than left to the engine default, because
	// the default AHUD draws nothing and the sim reads as a planner braking
	// for a detected pedestrian when nothing on screen says otherwise.
	HUDClass = AVrgHud::StaticClass();
}

void AVrgGameMode::StartPlay()
{
	Super::StartPlay();

	if (UWorld* World = GetWorld())
	{
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride =
			ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		// `-VrgMode=sim` spawns the driving scenario instead of the map viewer.
		// Two windows, two actors, one binary: the demo switches with a flag
		// rather than a second build.
		FString Mode;
		FParse::Value(FCommandLine::Get(), TEXT("VrgMode="), Mode);
		if (Mode.Equals(TEXT("sim"), ESearchCase::IgnoreCase))
		{
			World->SpawnActor<AVrgSimActor>(
				AVrgSimActor::StaticClass(), FTransform::Identity, Params);
		}
		else
		{
			SceneActor = World->SpawnActor<AVrgSceneActor>(
				AVrgSceneActor::StaticClass(), FTransform::Identity, Params);
		}

		if (APlayerController* PC = World->GetFirstPlayerController())
		{
			// Cursor VISIBLE, and input shared with the UI.
			//
			// This is a windowed viewer sitting beside a Rerun window that the
			// presenter has to click on. `FInputModeGameOnly` with a hidden
			// cursor captures the mouse to this window, so the pointer vanishes
			// and the other window cannot be reached without alt-tabbing --
			// which is not a thing anyone should be doing on stage.
			PC->bShowMouseCursor = true;
			FInputModeGameAndUI InputMode;
			InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
			InputMode.SetHideCursorDuringCapture(false);
			PC->SetInputMode(InputMode);
		}
	}
}
