// The standing disclaimer, drawn over whichever window is running.
//
// ⚑ WHY THIS EXISTS AT ALL.
//   In `-VrgMode=sim` the car yields to a scripted pedestrian, and it does so
//   from the SIM'S OWN pedestrian positions -- `AVrgSimActor::Peds`, authored
//   here. No VRgrid output reaches that decision, and VRgrid has no planner to
//   produce one. Watched without a caption, "person steps out, car brakes" is
//   read as perception detecting a pedestrian and a planner braking for it,
//   which is a claim this project does not make. The label makes the audience
//   read the window the way the presenter would describe it, and it keeps
//   doing that in the clips and screenshots nobody is standing beside.
//
// Canvas, not UMG: this project ships no .uasset, and a UMG widget wants one.
// `AHUD::DrawText` costs nothing, needs no asset, and cannot fail to load --
// which is the property that matters for a caption whose whole job is to be
// there when something else has gone wrong.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"

#include "VrgHud.generated.h"

UCLASS()
class VRGRIDVIEWER_API AVrgHud : public AHUD
{
	GENERATED_BODY()

public:
	AVrgHud();

	virtual void BeginPlay() override;
	virtual void DrawHUD() override;

	/** ON by default, and deliberately so: a disclaimer that has to be turned
	 *  on is a disclaimer that is off in every recording of the demo. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "VRgrid|HUD")
	bool bShowDisclaimer = true;

	/** `H` -- hide. Not bound anywhere else: the map viewer owns Space, the
	 *  arrows, Home, G, P, F, U and C, and the sim owns B and N. */
	UFUNCTION(BlueprintCallable, Category = "VRgrid|HUD")
	void ToggleDisclaimer();

private:
	void BindHudInput();

	/** True when `-VrgMode=sim` put the driving simulation on screen rather
	 *  than the map viewer. The two windows overclaim in different ways, so
	 *  they get different text. */
	bool bSimMode = false;

	/** The lines to draw, decided once in BeginPlay. */
	TArray<FString> Lines;
};
