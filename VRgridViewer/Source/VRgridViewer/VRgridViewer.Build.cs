using UnrealBuildTool;

public class VRgridViewer : ModuleRules
{
	public VRgridViewer(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"Json",          // scene.json manifest
			"JsonUtilities",
			"RenderCore",
			"ProceduralMeshComponent",
		});

		// ⚑ NOTHING IN THIS MODULE USES THESE THREE YET.
		//   The comment here used to read "the HUD reads stats.jsonl". No C++
		//   in this module reads stats.jsonl -- grep it and the only hits are
		//   doc comments describing what an export DIRECTORY contains. The
		//   file is written by the exporter for a per-frame readout that was
		//   never built on this side.
		//   Nor is the on-screen label a UMG widget: AVrgHud draws through
		//   AHUD/UCanvas, which needs only Engine. That was deliberate -- this
		//   project ships no .uasset, and UMG wants one.
		//   Kept as dependencies rather than removed, because a stats readout
		//   is still the obvious next thing to build here and the cost of an
		//   unused module reference is a link line, not behaviour.
		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Slate",
			"SlateCore",
			"UMG",
		});
	}
}
