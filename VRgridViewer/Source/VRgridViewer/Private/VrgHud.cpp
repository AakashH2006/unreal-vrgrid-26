#include "VrgHud.h"

#include "Components/InputComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace
{
	// ⚑ ASCII ONLY INSIDE TEXT(). Every other literal in this module is, and
	//   the .cpp files carry no BOM -- a raw em dash byte here would be read
	//   through whatever source charset the compiler happened to assume. The
	//   escape is the same character with none of that risk.
	const TCHAR* EmDash = TEXT("—");

	// Bottom LEFT. The chase camera keeps the vehicle centred and the sim's
	// own telemetry goes to the log rather than the screen, so this corner is
	// the one nothing else competes for.
	constexpr float MarginPx = 18.0f;
	constexpr float PadPx = 10.0f;

	// The label is a caption, not a headline: it has to be legible at the
	// 1600x900 the demo scripts launch at without covering the street. This is
	// the scale at that width; wider viewports get proportionally more, so it
	// stays the same physical size on screen rather than shrinking away.
	constexpr float ScaleAt1600 = 1.25f;
	constexpr float ReferenceWidthPx = 1600.0f;
}

AVrgHud::AVrgHud()
{
	PrimaryActorTick.bCanEverTick = false;
}

void AVrgHud::BeginPlay()
{
	Super::BeginPlay();

	// Read the mode the same way AVrgGameMode does, rather than being told:
	// one parse, one spelling, and the HUD cannot end up captioning the other
	// window because a constructor argument went missing.
	FString Mode;
	FParse::Value(FCommandLine::Get(), TEXT("VrgMode="), Mode);
	bSimMode = Mode.Equals(TEXT("sim"), ESearchCase::IgnoreCase);

	if (bSimMode)
	{
		// Two lines, because there are two separate things to say: what IS
		// taken from the data (the route and the ring schedule), and what is
		// not (everything that moves).
		Lines.Add(FString::Printf(
			TEXT("Visualisation %s route from KITTI seq 00, rings from the VRgrid schedule."),
			EmDash));
		Lines.Add(TEXT("Traffic, pedestrians and vehicle behaviour are simulated, "
		               "not VRgrid output."));
	}
	else
	{
		// The map viewer draws the exported cells, so it does not invent
		// behaviour -- but it is still not where any number comes from.
		Lines.Add(FString::Printf(
			TEXT("Same run as the Rerun window %s rendering only, no numbers produced here."),
			EmDash));
	}

	BindHudInput();

	UE_LOG(LogTemp, Log, TEXT("VRgrid: disclaimer ON (%s mode) -- H hides it"),
	       bSimMode ? TEXT("sim") : TEXT("map viewer"));
}

void AVrgHud::BindHudInput()
{
	APlayerController* PC = GetOwningPlayerController();
	if (PC == nullptr)
	{
		// Not fatal, and deliberately not treated as such: the label defaults
		// to ON, so losing the key costs the ability to HIDE it, never the
		// ability to show it.
		UE_LOG(LogTemp, Warning,
		       TEXT("VRgrid: no player controller for the HUD -- the disclaimer "
		            "is drawn but H will not hide it."));
		return;
	}
	EnableInput(PC);
	if (InputComponent != nullptr)
	{
		InputComponent->BindKey(EKeys::H, IE_Pressed, this, &AVrgHud::ToggleDisclaimer);
	}
}

void AVrgHud::ToggleDisclaimer()
{
	bShowDisclaimer = !bShowDisclaimer;
	UE_LOG(LogTemp, Log, TEXT("VRgrid: disclaimer %s"),
	       bShowDisclaimer ? TEXT("shown") : TEXT("hidden"));
}

void AVrgHud::DrawHUD()
{
	Super::DrawHUD();

	if (!bShowDisclaimer || Canvas == nullptr || Lines.Num() == 0)
	{
		return;
	}

	UFont* Font = GEngine ? GEngine->GetMediumFont() : nullptr;
	if (Font == nullptr && GEngine != nullptr)
	{
		Font = GEngine->GetLargeFont();
	}
	if (Font == nullptr)
	{
		return;
	}

	const float Scale = FMath::Max(1.0f, (Canvas->SizeX / ReferenceWidthPx) * ScaleAt1600);

	// Measure first, so the backing panel is the size of the text rather than
	// a guess that clips the long line at one resolution and floats at another.
	float BlockW = 0.0f;
	float LineH = 0.0f;
	TArray<float> Heights;
	Heights.Reserve(Lines.Num());
	for (const FString& Line : Lines)
	{
		float W = 0.0f;
		float H = 0.0f;
		GetTextSize(Line, W, H, Font, Scale);
		BlockW = FMath::Max(BlockW, W);
		Heights.Add(H);
		LineH = FMath::Max(LineH, H);
	}

	float BlockH = 0.0f;
	for (const float H : Heights)
	{
		BlockH += H;
	}
	// A little air between the lines, or the two sim lines read as one.
	const float LineGap = LineH * 0.18f;
	BlockH += LineGap * FMath::Max(0, Lines.Num() - 1);

	const float PanelX = MarginPx;
	const float PanelY = Canvas->SizeY - MarginPx - BlockH - PadPx * 2.0f;

	// ⚑ A PANEL, NOT JUST TEXT. The sim is a DAYLIGHT street -- white kerbs,
	//   pale tarmac, bright sky -- and white text on it is legible in some
	//   frames and gone in others. The one thing this label must never do is
	//   disappear into the scene behind it, so it carries its own background.
	DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.62f),
	         PanelX, PanelY, BlockW + PadPx * 2.0f, BlockH + PadPx * 2.0f);

	float Y = PanelY + PadPx;
	for (int32 i = 0; i < Lines.Num(); ++i)
	{
		DrawText(Lines[i], FLinearColor(0.96f, 0.96f, 0.96f, 1.0f),
		         PanelX + PadPx, Y, Font, Scale, false);
		Y += Heights[i] + LineGap;
	}
}
