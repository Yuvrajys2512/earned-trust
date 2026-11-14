// Earned Trust — receipts written by the REVIEWER (not the author agent) for ju26-issue-2283.
// Copied into tests/MessagePack.SourceGenerator.Tests/ of both the BASE and HEAD worktrees.
// #2283 asks to stop a crash on closed generic value types from a referenced assembly. The PR also wraps
// TypeCollector's diagnostic callback so that EVERY diagnostic not located in this compilation's syntax
// trees is dropped. These receipts check what that global filter does to cases the requirement never mentions.
#nullable enable

using System.Collections.Immutable;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using MessagePack.SourceGenerator.Analyzers;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.Diagnostics;
using Microsoft.CodeAnalysis.Testing;

namespace MessagePack.SourceGenerator.Tests;

public class EtScopeDriftReceiptsTests
{
    private readonly ITestOutputHelper logger;

    public EtScopeDriftReceiptsTests(ITestOutputHelper logger) => this.logger = logger;

    private const string LibSource = """
        using MessagePack;
        namespace Lib
        {
            public class NotSerializable { public int X { get; set; } }

            // non-generic: the analyzer does not descend into it from another assembly (base and head alike)
            [MessagePackObject]
            public class Wrapper
            {
                [Key(0)] public NotSerializable Inner { get; set; }
            }

            // closed generic value type: the analyzer DOES descend into it (the #2283 crash path).
            // Same shape as the agent's UnkeyedMember test: one member has no [Key].
            [MessagePackObject]
            public struct Box<T>
            {
                [Key(0)] public T Value { get; set; }
                public int Unkeyed { get; set; }
            }
        }
        """;

    private const string AppNonGeneric = """
        using MessagePack;
        namespace App
        {
            [MessagePackObject]
            public class Order
            {
                [Key(0)] public Lib.Wrapper Payload { get; set; }
            }
        }
        """;

    private const string AppClosedGeneric = """
        using MessagePack;
        namespace App
        {
            [MessagePackObject]
            public class Order
            {
                [Key(0)] public Lib.Box<int> Payload { get; set; }
            }
        }
        """;

    private async Task<ImmutableArray<Diagnostic>> AnalyzeAppAsync(string AppSource, string evidenceName)
    {
        var refs = await ReferenceAssemblies.Net.Net80.ResolveAsync(LanguageNames.CSharp, CancellationToken.None);
        var all = refs.AddRange(ReferencesHelper.GetReferences(ReferencesSet.MessagePack));
        var parse = new CSharpParseOptions(LanguageVersion.Latest);
        var lib = CSharpCompilation.Create("Lib", new[] { CSharpSyntaxTree.ParseText(LibSource, parse) }, all,
            new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));
        using var ms = new MemoryStream();
        var emit = lib.Emit(ms);
        Assert.True(emit.Success, string.Join("\n", emit.Diagnostics));
        var app = CSharpCompilation.Create("App", new[] { CSharpSyntaxTree.ParseText(AppSource, parse) },
            all.Add(MetadataReference.CreateFromImage(ms.ToArray())), new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));
        var analyzers = ImmutableArray.Create<DiagnosticAnalyzer>(new MsgPack00xMessagePackAnalyzer());
        var diags = await app.WithAnalyzers(analyzers).GetAllDiagnosticsAsync();
        var report = string.Join("\n", diags.Where(d => d.Id.StartsWith("MsgPack") || d.Id == "AD0001")
            .Select(d => $"{d.Id} {d.Severity} @ {(d.Location.IsInSource ? "source" : d.Location.Kind.ToString())}: {d.GetMessage()}"));
        this.logger.WriteLine(report.Length == 0 ? "(no MessagePack diagnostics)" : report);
        string? dir = System.Environment.GetEnvironmentVariable("ET_EVIDENCE_DIR");
        if (!string.IsNullOrEmpty(dir))
        {
            Directory.CreateDirectory(dir);
            File.WriteAllText(Path.Combine(dir, evidenceName + ".txt"), report.Length == 0 ? "(no MessagePack diagnostics)" : report);
        }

        return diags;
    }

    // Fact check (expected placebo): our first hypothesis was that the filter silences this case. Executed: neither
    // side reports anything, because the analyzer never descends into a non-generic referenced type (LESSONS L-17).
    [Fact]
    public async Task Fact_ReferencedNonGenericType_MembersAreNotAnalyzed()
    {
        var diags = await this.AnalyzeAppAsync(AppNonGeneric, "referenced-nongeneric");
        Assert.DoesNotContain(diags, d => d.Id.StartsWith("MsgPack") || d.Id == "AD0001");
    }

    // The scope-drift receipt. #2283 asks: stop crashing. Without the crash, the analyzer has a real finding here:
    // MsgPack004 (an error) for Box<int>.Unkeyed, which the user's compilation will generate a formatter for.
    // Base: crashes (AD0001). Head: silent, because the PR's global filter drops every diagnostic located outside
    // this compilation. Counterfactual (head with only the filter line reverted, scripts/verify_2283_base.sh): passes.
    [Fact]
    public async Task ReferencedClosedGeneric_UnkeyedMember_IsReportedNotCrashedOrDropped()
    {
        var diags = await this.AnalyzeAppAsync(AppClosedGeneric, "referenced-closed-generic-unkeyed");
        Assert.DoesNotContain(diags, d => d.Id == "AD0001");
        Assert.Contains(diags, d => d.Id == "MsgPack004");
    }
}
