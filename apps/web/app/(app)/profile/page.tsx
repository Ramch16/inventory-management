"use client";

import { CertificationsSection } from "@/components/profile/certifications-section";
import { EducationSection } from "@/components/profile/education-section";
import { ExperienceSection } from "@/components/profile/experience-section";
import { ProfileDetailsForm } from "@/components/profile/profile-details-form";
import { SkillsSection } from "@/components/profile/skills-section";
import { WorkAuthorizationForm } from "@/components/profile/work-authorization-form";
import { Alert } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useCertifications,
  useCompleteness,
  useEducation,
  useExperience,
  useProfile,
  useSkills,
} from "@/hooks/use-profile";

export default function ProfilePage() {
  const profile = useProfile();
  const completeness = useCompleteness();
  const experience = useExperience();
  const education = useEducation();
  const skills = useSkills();
  const certifications = useCertifications();

  if (profile.isLoading || !profile.data) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Profile</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Everything an application can say about you comes from this page. Nothing here is
          generated.
        </p>
      </div>

      {completeness.data ? (
        <div className="rounded-lg border p-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-medium">Profile completeness</span>
            <span className="tabular text-muted-foreground">{completeness.data.score}%</span>
          </div>
          <Progress value={completeness.data.score} />
          {completeness.data.missing.length > 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Still missing: {completeness.data.missing.join(", ")}
            </p>
          ) : (
            <p className="mt-2 text-xs text-success">Your profile is complete.</p>
          )}
        </div>
      ) : null}

      <Tabs defaultValue="details">
        <TabsList className="flex-wrap">
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="authorization">Work authorization</TabsTrigger>
          <TabsTrigger value="experience">Experience</TabsTrigger>
          <TabsTrigger value="education">Education</TabsTrigger>
          <TabsTrigger value="skills">Skills</TabsTrigger>
        </TabsList>

        <TabsContent value="details">
          <ProfileDetailsForm profile={profile.data} />
        </TabsContent>

        <TabsContent value="authorization">
          <WorkAuthorizationForm value={profile.data.work_authorization} />
        </TabsContent>

        <TabsContent value="experience">
          {experience.isError ? (
            <Alert variant="destructive">Experience could not be loaded.</Alert>
          ) : (
            <ExperienceSection items={experience.data ?? []} />
          )}
        </TabsContent>

        <TabsContent value="education">
          <EducationSection items={education.data ?? []} />
        </TabsContent>

        <TabsContent value="skills" className="space-y-6">
          <SkillsSection items={skills.data ?? []} />
          <CertificationsSection items={certifications.data ?? []} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
